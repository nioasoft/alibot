import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.models import Deal, PublishQueueItem, RawMessage
from bot.publisher import DealPublisher


def _seed_deal(db_session, deal_id: int = 1, platform: str = "telegram", target_ref: str = "@my_channel"):
    raw = RawMessage(
        source_group="@test",
        telegram_message_id=deal_id,
        raw_text="text",
        has_images=False,
        received_at=datetime.datetime.now(datetime.UTC),
        status="processed",
    )
    db_session.add(raw)
    db_session.flush()

    deal = Deal(
        raw_message_id=raw.id,
        product_name="Test Product",
        original_text="orig",
        rewritten_text="🔥 Test deal ₪45",
        price=45.0,
        currency="ILS",
        category="tech",
        product_link="https://aliexpress.com/item/123.html",
        text_hash=f"hash_{deal_id}",
        source_group="@test",
        created_at=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(deal)
    db_session.flush()

    queue_item = PublishQueueItem(
        deal_id=deal.id,
        target_group=target_ref,
        destination_key=f"{platform}_{deal_id}",
        platform=platform,
        target_ref=target_ref,
        status="queued",
        scheduled_after=datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=1),
    )
    db_session.add(queue_item)
    db_session.commit()
    return deal, queue_item


@pytest.fixture
def publisher(db_session):
    telegram = MagicMock()
    telegram.send_deal = AsyncMock(return_value=99999)

    whatsapp = MagicMock()
    whatsapp.send_deal = AsyncMock(return_value=True)

    web = MagicMock()
    web.send_deal = AsyncMock(return_value=True)

    return DealPublisher(
        session=db_session,
        min_delay=300,
        max_delay=600,
        max_posts_per_hour=4,
        quiet_hours_start=23,
        quiet_hours_end=7,
        telegram_publisher=telegram,
        whatsapp_publisher=whatsapp,
        web_publisher=web,
    )


class TestQueuePicking:
    def test_picks_oldest_queued_item(self, publisher: DealPublisher, db_session):
        _seed_deal(db_session, deal_id=1)
        _seed_deal(db_session, deal_id=2)

        item = publisher.pick_next()
        assert item is not None
        assert item.status == "queued"

    def test_respects_scheduled_after(self, publisher: DealPublisher, db_session):
        _, qi = _seed_deal(db_session, deal_id=1)
        qi.scheduled_after = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)
        db_session.commit()

        assert publisher.pick_next() is None


class TestQuietHours:
    def test_is_quiet_at_midnight(self, publisher: DealPublisher):
        assert publisher.is_quiet_hour(datetime.datetime(2026, 1, 1, 0, 0)) is True

    def test_is_not_quiet_at_noon(self, publisher: DealPublisher):
        assert publisher.is_quiet_hour(datetime.datetime(2026, 1, 1, 12, 0)) is False


class TestRateLimit:
    def test_rate_limit_blocks_after_max(self, publisher: DealPublisher, db_session):
        for i in range(4):
            _, qi = _seed_deal(db_session, deal_id=100 + i)
            qi.status = "published"
            qi.published_at = datetime.datetime.now(datetime.UTC)
            db_session.commit()

        assert publisher.is_rate_limited("@my_channel") is True

    def test_rate_limit_allows_under_max(self, publisher: DealPublisher):
        assert publisher.is_rate_limited("@my_channel") is False


@pytest.mark.asyncio
class TestPublishExecution:
    async def test_publish_marks_telegram_item_as_published(self, publisher: DealPublisher, db_session):
        deal, qi = _seed_deal(db_session, deal_id=1, platform="telegram")

        await publisher.publish_one(qi, deal)

        db_session.refresh(qi)
        assert qi.status == "published"
        assert qi.message_id == 99999
        assert qi.published_at is not None

    async def test_publish_whatsapp_item_marks_published(self, publisher: DealPublisher, db_session):
        deal, qi = _seed_deal(db_session, deal_id=2, platform="whatsapp", target_ref="120@g.us")

        await publisher.publish_one(qi, deal)

        db_session.refresh(qi)
        assert qi.status == "published"
        assert qi.message_id is None
        publisher._whatsapp.send_deal.assert_awaited_once()
