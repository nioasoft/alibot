import datetime
from sqlalchemy import select
from bot.models import RawMessage, Deal, PublishQueueItem, DailyStat


def test_create_raw_message(db_session):
    msg = RawMessage(
        source_group="@test_group",
        telegram_message_id=12345,
        raw_text="Great deal! https://s.click.aliexpress.com/e/_abc123",
        has_images=True,
        received_at=datetime.datetime.now(datetime.UTC),
        status="pending",
    )
    db_session.add(msg)
    db_session.commit()

    result = db_session.execute(select(RawMessage)).scalar_one()
    assert result.source_group == "@test_group"
    assert result.status == "pending"
    assert result.telegram_message_id == 12345


def test_create_deal_linked_to_raw_message(db_session):
    msg = RawMessage(
        source_group="@test",
        telegram_message_id=1,
        raw_text="text",
        has_images=False,
        received_at=datetime.datetime.now(datetime.UTC),
        status="processed",
    )
    db_session.add(msg)
    db_session.flush()

    deal = Deal(
        raw_message_id=msg.id,
        product_id="1005003091506814",
        product_name="Wireless Earbuds",
        original_text="Original deal text",
        rewritten_text="Rewritten text",
        price=45.90,
        currency="ILS",
        category="tech",
        product_link="https://aliexpress.com/item/1005003091506814.html",
        text_hash="abc123hash",
        source_group="@test",
        created_at=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(deal)
    db_session.commit()

    result = db_session.execute(select(Deal)).scalar_one()
    assert result.product_id == "1005003091506814"
    assert result.raw_message_id == msg.id
    assert result.price == 45.90


def test_create_publish_queue_item(db_session):
    msg = RawMessage(
        source_group="@test",
        telegram_message_id=1,
        raw_text="text",
        has_images=False,
        received_at=datetime.datetime.now(datetime.UTC),
        status="processed",
    )
    db_session.add(msg)
    db_session.flush()

    deal = Deal(
        raw_message_id=msg.id,
        product_name="Test",
        original_text="orig",
        rewritten_text="new",
        price=10.0,
        currency="ILS",
        category="tech",
        product_link="https://aliexpress.com/item/123.html",
        text_hash="hash1",
        source_group="@test",
        created_at=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(deal)
    db_session.flush()

    queue_item = PublishQueueItem(
        deal_id=deal.id,
        target_group="@my_channel",
        status="queued",
        scheduled_after=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(queue_item)
    db_session.commit()

    result = db_session.execute(select(PublishQueueItem)).scalar_one()
    assert result.status == "queued"
    assert result.deal_id == deal.id


def test_daily_stats_upsert(db_session):
    today = datetime.date.today()
    stat = DailyStat(
        date=today,
        deals_seen=10,
        deals_processed=8,
        deals_published=5,
        deals_skipped_dup=2,
        deals_skipped_error=1,
        api_calls=8,
    )
    db_session.add(stat)
    db_session.commit()

    result = db_session.execute(
        select(DailyStat).where(DailyStat.date == today)
    ).scalar_one()
    assert result.deals_seen == 10
    assert result.deals_published == 5
