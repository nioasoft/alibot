from __future__ import annotations

import datetime
from pathlib import Path

import pytest
import respx
from httpx import Response

from bot.facebook_publisher import FacebookPublisher
from bot.models import Deal, FacebookGroupState


class _NotifyRecorder:
    """Async-callable that records the messages it was sent."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    async def __call__(self, text: str) -> None:
        self.messages.append(text)


_GROUP_URL = "https://www.facebook.com/groups/test"


def _make_deal() -> Deal:
    return Deal(
        id=1,
        raw_message_id=1,
        product_id="1005001",
        product_name="Sample Deal",
        original_text="orig",
        rewritten_text="rewritten",
        price=49.9,
        original_price=None,
        currency="ILS",
        shipping=None,
        category="tech",
        ali_category_raw=None,
        category_source=None,
        affiliate_account_key=None,
        affiliate_link="https://s.click.aliexpress.com/e/_sample",
        product_link="https://www.aliexpress.com/item/1005001.html",
        image_hash=None,
        image_path="/tmp/sample.jpg",
        text_hash="hash",
        source_group="@source",
        created_at=datetime.datetime.now(datetime.UTC),
    )


def _make_marketing_heavy_deal() -> Deal:
    deal = _make_deal()
    deal.rewritten_text = (
        "🔝 שדרגו את האימון שלכם עם חבל הקפיצה החדש!\n"
        "קל לנשיאה, מתכוונן ומתאים לאימון בבית או בחוץ.\n"
        "💰 מחיר: $5.72 (כ-₪17.05)\n"
        "🚚 משלוח חינם"
    )
    deal.price = 17.05
    deal.currency = "ILS"
    deal.shipping = "חינם"
    return deal


@pytest.mark.asyncio
async def test_send_deal_includes_image_path_and_updated_site_text() -> None:
    publisher = FacebookPublisher(
        service_url="http://facebook.test",
        site_url="https://www.dilim.net/",
        comment_on_post=False,
    )

    with respx.mock(assert_all_called=True) as router:
        route = router.post("http://facebook.test/publish").mock(
            return_value=Response(200, json={"ok": True})
        )

        ok = await publisher.send_deal(
            deal=_make_deal(),
            group_url="https://www.facebook.com/groups/test",
        )

    assert ok is True
    payload = route.calls[0].request.content.decode()
    assert f'"image_path":"{Path("/tmp/sample.jpg").resolve()}"' in payload
    # link-in-body mode posts the compact text (description + normalized price)
    assert '"text":"rewritten\\nמחיר: ₪49.9"' in payload
    assert '"append_text":"\\n\\n🌐 להצטרפות לקבוצות לפי תחומי עניין: https://www.dilim.net\\n🛒 לרכישה: https://s.click.aliexpress.com/e/_sample"' in payload
    assert "הצטרפות לקבוצות לפי תחומי עניין" in payload
    assert '"comment_text":""' in payload
    assert '"comment_on_post":false' in payload


@pytest.mark.asyncio
async def test_send_deal_defaults_to_first_comment_for_link() -> None:
    publisher = FacebookPublisher(
        service_url="http://facebook.test",
        site_url="https://www.dilim.net/",
    )

    with respx.mock(assert_all_called=True) as router:
        route = router.post("http://facebook.test/publish").mock(
            return_value=Response(200, json={"ok": True})
        )

        ok = await publisher.send_deal(
            deal=_make_deal(),
            group_url="https://www.facebook.com/groups/test",
        )

    assert ok is True
    payload = route.calls[0].request.content.decode()
    assert '"append_text":""' in payload
    assert '"comment_text":"🛒 קישור לרכישה: https://s.click.aliexpress.com/e/_sample"' in payload
    assert '"comment_on_post":true' in payload


@pytest.mark.asyncio
async def test_send_deal_moves_links_to_comment_payload_when_enabled() -> None:
    publisher = FacebookPublisher(
        service_url="http://facebook.test",
        site_url="https://www.dilim.net/",
        comment_on_post=True,
    )

    with respx.mock(assert_all_called=True) as router:
        route = router.post("http://facebook.test/publish").mock(
            return_value=Response(200, json={"ok": True})
        )

        ok = await publisher.send_deal(
            deal=_make_deal(),
            group_url="https://www.facebook.com/groups/test",
        )

    assert ok is True
    payload = route.calls[0].request.content.decode()
    assert '"text":"rewritten\\nמחיר: ₪49.9\\n🛒 לרכישה: בתגובה הראשונה"' in payload
    assert '"append_text":""' in payload
    assert '"comment_text":"🛒 קישור לרכישה: https://s.click.aliexpress.com/e/_sample"' in payload
    assert '"comment_on_post":true' in payload


@pytest.mark.asyncio
async def test_send_deal_uses_compact_facebook_text_when_comment_mode_enabled() -> None:
    publisher = FacebookPublisher(
        service_url="http://facebook.test",
        site_url="https://www.dilim.net/",
        comment_on_post=True,
    )

    with respx.mock(assert_all_called=True) as router:
        route = router.post("http://facebook.test/publish").mock(
            return_value=Response(200, json={"ok": True})
        )

        ok = await publisher.send_deal(
            deal=_make_marketing_heavy_deal(),
            group_url="https://www.facebook.com/groups/test",
        )

    assert ok is True
    payload = route.calls[0].request.content.decode()
    assert 'שדרגו את האימון שלכם עם חבל הקפיצה החדש' in payload
    assert 'קל לנשיאה, מתכוונן ומתאים לאימון בבית או בחוץ.' in payload
    assert 'מחיר: ₪17.05' in payload
    assert 'משלוח: חינם' in payload
    assert 'לרכישה: בתגובה הראשונה' in payload
    assert '💰 מחיר: $5.72 (כ-₪17.05)' not in payload
    assert '🚚 משלוח חינם' not in payload


@pytest.mark.asyncio
async def test_pending_approval_marks_group_and_notifies(db_session) -> None:
    notify = _NotifyRecorder()
    publisher = FacebookPublisher(
        service_url="http://facebook.test",
        site_url="https://www.dilim.net/",
        comment_on_post=True,
        session=db_session,
        notify_func=notify,
    )

    with respx.mock(assert_all_called=True) as router:
        router.post("http://facebook.test/publish").mock(
            return_value=Response(200, json={"ok": True, "pending": True}),
        )
        ok = await publisher.send_deal(deal=_make_deal(), group_url=_GROUP_URL)

    assert ok is True
    state = db_session.get(FacebookGroupState, _GROUP_URL)
    assert state is not None and state.approval_required is True
    assert len(notify.messages) == 1
    assert "אישור" in notify.messages[0]


@pytest.mark.asyncio
async def test_known_approval_group_posts_link_in_body(db_session) -> None:
    db_session.add(
        FacebookGroupState(
            group_url=_GROUP_URL,
            approval_required=True,
            updated_at=datetime.datetime.now(datetime.UTC),
        )
    )
    db_session.commit()

    publisher = FacebookPublisher(
        service_url="http://facebook.test",
        site_url="https://www.dilim.net/",
        comment_on_post=True,  # global default is first-comment...
        session=db_session,
    )

    with respx.mock(assert_all_called=True) as router:
        route = router.post("http://facebook.test/publish").mock(
            return_value=Response(200, json={"ok": True}),
        )
        ok = await publisher.send_deal(deal=_make_deal(), group_url=_GROUP_URL)

    assert ok is True
    payload = route.calls[0].request.content.decode()
    # ...but a known approval group must put the link in the post body, not a comment.
    assert '"comment_on_post":false' in payload
    assert '"comment_text":""' in payload
    assert "🛒 לרכישה: https://s.click.aliexpress.com/e/_sample" in payload


@pytest.mark.asyncio
async def test_personal_profile_fallback_notifies(db_session) -> None:
    notify = _NotifyRecorder()
    publisher = FacebookPublisher(
        service_url="http://facebook.test",
        site_url="https://www.dilim.net/",
        session=db_session,
        notify_func=notify,
    )

    with respx.mock(assert_all_called=True) as router:
        router.post("http://facebook.test/publish").mock(
            return_value=Response(
                200,
                json={"ok": True, "postedAsPage": False, "identityMode": "profile-default"},
            ),
        )
        ok = await publisher.send_deal(deal=_make_deal(), group_url=_GROUP_URL)

    assert ok is True
    assert len(notify.messages) == 1
    assert "פרופיל" in notify.messages[0]


@pytest.mark.asyncio
async def test_page_unverified_session_does_not_notify(db_session) -> None:
    """page-unverified-session is a known false-negative (page name == group name)."""
    notify = _NotifyRecorder()
    publisher = FacebookPublisher(
        service_url="http://facebook.test",
        site_url="https://www.dilim.net/",
        session=db_session,
        notify_func=notify,
    )

    with respx.mock(assert_all_called=True) as router:
        router.post("http://facebook.test/publish").mock(
            return_value=Response(
                200,
                json={"ok": True, "postedAsPage": False, "identityMode": "page-unverified-session"},
            ),
        )
        ok = await publisher.send_deal(deal=_make_deal(), group_url=_GROUP_URL)

    assert ok is True
    assert notify.messages == []


@pytest.mark.asyncio
async def test_send_deal_without_session_is_backward_compatible() -> None:
    """No session/notify wired → behaves exactly as before (returns bool, no crash)."""
    publisher = FacebookPublisher(
        service_url="http://facebook.test",
        site_url="https://www.dilim.net/",
    )

    with respx.mock(assert_all_called=True) as router:
        router.post("http://facebook.test/publish").mock(
            return_value=Response(200, json={"ok": True, "pending": True}),
        )
        ok = await publisher.send_deal(deal=_make_deal(), group_url=_GROUP_URL)

    assert ok is True
