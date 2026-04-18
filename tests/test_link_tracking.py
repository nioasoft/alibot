import datetime

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


def test_get_or_create_tracked_url_reuses_existing_token(db_session) -> None:
    deal, queue_item = _seed_deal_and_queue(db_session)
    tracker = LinkTracker(db_session, base_url="https://trk.dilim.net")

    first = tracker.get_or_create_tracked_url(deal, queue_item, deal.affiliate_link)
    second = tracker.get_or_create_tracked_url(deal, queue_item, deal.affiliate_link)

    assert first == second
    tokens = db_session.query(AffiliateLinkToken).all()
    assert len(tokens) == 1
    assert first.endswith(tokens[0].token)


def test_get_or_create_tracked_url_returns_raw_url_when_disabled(db_session) -> None:
    deal, queue_item = _seed_deal_and_queue(db_session)
    tracker = LinkTracker(db_session, base_url="")

    result = tracker.get_or_create_tracked_url(deal, queue_item, deal.affiliate_link)

    assert result == deal.affiliate_link
    assert db_session.query(AffiliateLinkToken).count() == 0
