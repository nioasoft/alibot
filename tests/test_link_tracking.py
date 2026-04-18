import datetime

import httpx
import pytest
import respx

from bot.link_tracking import LinkTracker
from bot.models import AffiliateLinkToken, Deal, PublishQueueItem, RawMessage


def _seed_deal_and_queue(db_session):
    now = datetime.datetime.now(datetime.UTC)
    raw = RawMessage(
        source_group="@source",
        telegram_message_id=1,
        raw_text="text",
        has_images=False,
        received_at=now,
        status="processed",
        error_message=None,
    )
    db_session.add(raw)
    db_session.flush()

    deal = Deal(
        raw_message_id=raw.id,
        product_name="Tracked Product",
        original_text="orig",
        rewritten_text="rewritten",
        price=10.0,
        original_price=None,
        currency="USD",
        shipping=None,
        category="tech",
        ali_category_raw=None,
        category_source=None,
        affiliate_account_key="primary",
        affiliate_link="https://s.click.aliexpress.com/e/_tracked",
        product_link="https://www.aliexpress.com/item/1005001.html",
        image_hash=None,
        image_path=None,
        text_hash="hash",
        source_group="@source",
        created_at=now,
    )
    db_session.add(deal)
    db_session.flush()

    queue_item = PublishQueueItem(
        deal_id=deal.id,
        target_group="@target",
        destination_key="tg_main",
        platform="telegram",
        target_ref="@target",
        status="queued",
        priority=0,
        scheduled_after=now,
        published_at=None,
        message_id=None,
        error_message=None,
    )
    db_session.add(queue_item)
    db_session.commit()
    return deal, queue_item


@pytest.mark.asyncio
async def test_get_or_create_tracked_url_uses_remote_tracking_api(db_session) -> None:
    deal, queue_item = _seed_deal_and_queue(db_session)
    tracker = LinkTracker(
        db_session,
        base_url="https://trk.dilim.net",
        api_secret="tracker-secret",
    )

    with respx.mock:
        route = respx.post("https://trk.dilim.net/api/tracking-links").mock(
            return_value=httpx.Response(
                201,
                json={
                    "token": "abc123",
                    "trackedUrl": "https://trk.dilim.net/go/abc123",
                    "reused": False,
                },
            )
        )
        result = await tracker.get_or_create_tracked_url(
            deal,
            queue_item,
            deal.affiliate_link,
        )

    assert result == "https://trk.dilim.net/go/abc123"
    assert route.called
    payload = route.calls[0].request.read().decode("utf-8")
    assert "\"category\":\"tech\"" in payload
    assert "\"queueItemId\":1" in payload
    assert db_session.query(AffiliateLinkToken).count() == 0


@pytest.mark.asyncio
async def test_get_or_create_tracked_url_returns_raw_url_when_disabled(db_session) -> None:
    deal, queue_item = _seed_deal_and_queue(db_session)
    tracker = LinkTracker(db_session, base_url="")

    result = await tracker.get_or_create_tracked_url(deal, queue_item, deal.affiliate_link)

    assert result == deal.affiliate_link
    assert db_session.query(AffiliateLinkToken).count() == 0
