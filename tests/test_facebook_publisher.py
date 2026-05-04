from __future__ import annotations

import datetime
from pathlib import Path

import pytest
import respx
from httpx import Response

from bot.facebook_publisher import FacebookPublisher
from bot.models import Deal


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
    assert '"text":"rewritten"' in payload
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
