import datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx

from bot.config import DestinationConfig, InviteLinkConfig
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

    facebook = MagicMock()
    facebook.send_deal = AsyncMock(return_value=True)

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
        facebook_publisher=facebook,
        web_publisher=web,
        site_url="https://www.dilim.net/",
        tracking_base_url="https://trk.dilim.net",
        tracking_api_secret="tracker-secret",
        invite_links=[
            InviteLinkConfig(
                url="https://t.me/test",
                label="ערוץ הטלגרם",
                platform="telegram",
                footer_label="📢 להצטרפות לטלגרם",
            )
        ],
        destinations={
            "tg_main": DestinationConfig(
                key="tg_main",
                enabled=True,
                platform="telegram",
                target="@main",
                categories=["*"],
            ),
            "wa_tech": DestinationConfig(
                key="wa_tech",
                enabled=True,
                platform="whatsapp",
                target="120@g.us",
                categories=["tech"],
            ),
            "fb_beer_sheva_together": DestinationConfig(
                key="fb_beer_sheva_together",
                enabled=True,
                platform="facebook",
                target="https://www.facebook.com/groups/deals20",
                categories=["*"],
                min_publish_interval_minutes=120,
            ),
        },
        weekend_reduced_rate_factor=0.3,
        weekend_reduced_start_weekday=4,
        weekend_reduced_start_hour=18,
        weekend_reduced_end_weekday=5,
        weekend_reduced_end_hour=18,
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

    def test_prefers_target_that_has_been_idle_longer_when_priority_is_equal(
        self, publisher: DealPublisher, db_session
    ):
        _, qi1 = _seed_deal(db_session, deal_id=10, platform="whatsapp", target_ref="group-a")
        _, qi2 = _seed_deal(db_session, deal_id=11, platform="whatsapp", target_ref="group-b")
        _, published = _seed_deal(db_session, deal_id=12, platform="whatsapp", target_ref="group-a")

        qi1.priority = 50
        qi2.priority = 50
        qi1.scheduled_after = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=10)
        qi2.scheduled_after = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=10)
        published.status = "published"
        published.published_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
        db_session.commit()

        next_item = publisher.pick_next()
        assert next_item is not None
        assert next_item.target_ref == "group-b"

    def test_can_pick_main_and_category_queues_separately(
        self, publisher: DealPublisher, db_session
    ):
        _, main_item = _seed_deal(db_session, deal_id=20, platform="telegram", target_ref="@main")
        _, category_item = _seed_deal(db_session, deal_id=21, platform="whatsapp", target_ref="120@g.us")
        main_item.destination_key = "tg_main"
        category_item.destination_key = "wa_tech"
        main_item.priority = 70
        category_item.priority = 90
        db_session.commit()

        assert publisher.pick_next(queue_lane="main").id == main_item.id
        assert publisher.pick_next(queue_lane="category").id == category_item.id


class TestSocialFooter:
    def test_build_social_text_adds_rotating_invite_and_domain(
        self, publisher: DealPublisher, db_session
    ):
        deal, _ = _seed_deal(db_session, deal_id=77, platform="whatsapp", target_ref="120@g.us")

        text = publisher._build_social_text(deal, "https://trk.dilim.net/go/demo")

        assert "🛒 לרכישה: https://trk.dilim.net/go/demo" in text
        assert "📢 להצטרפות לטלגרם: https://t.me/test" in text
        assert text.endswith("🌐 להצטרפות לקבוצות לפי תחומי עניין: https://www.dilim.net/")


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

    def test_destination_min_interval_blocks_recent_publish(self, publisher: DealPublisher, db_session):
        _, recent = _seed_deal(
            db_session,
            deal_id=150,
            platform="facebook",
            target_ref="https://www.facebook.com/groups/deals20",
        )
        recent.destination_key = "fb_beer_sheva_together"
        recent.status = "published"
        recent.published_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=90)
        db_session.commit()

        assert publisher.is_rate_limited(
            "https://www.facebook.com/groups/deals20",
            "fb_beer_sheva_together",
        ) is True

    def test_weekend_reduction_limits_non_facebook_to_thirty_percent(
        self, publisher: DealPublisher, db_session
    ):
        for i in range(3):
            _, qi = _seed_deal(
                db_session,
                deal_id=160 + i,
                platform="telegram",
                target_ref="@main",
            )
            qi.destination_key = "tg_main"
            qi.status = "published"
            qi.published_at = datetime.datetime(2026, 4, 18, 8, 30, tzinfo=datetime.UTC)
            db_session.commit()

        assert publisher.is_rate_limited(
            "@main",
            "tg_main",
            now=datetime.datetime(2026, 4, 18, 12, 0),
        ) is True

    def test_weekend_reduction_does_not_apply_outside_window(
        self, publisher: DealPublisher, db_session
    ):
        for i in range(3):
            _, qi = _seed_deal(
                db_session,
                deal_id=170 + i,
                platform="telegram",
                target_ref="@main",
            )
            qi.destination_key = "tg_main"
            qi.status = "published"
            qi.published_at = datetime.datetime(2026, 4, 17, 12, 30, tzinfo=datetime.UTC)
            db_session.commit()

        assert publisher.is_rate_limited(
            "@main",
            "tg_main",
            now=datetime.datetime(2026, 4, 17, 16, 0),
        ) is False


@pytest.mark.asyncio
class TestPublishExecution:
    async def test_publish_marks_telegram_item_as_published(self, publisher: DealPublisher, db_session):
        deal, qi = _seed_deal(db_session, deal_id=1, platform="telegram")

        with respx.mock:
            respx.post("https://trk.dilim.net/api/tracking-links").mock(
                return_value=httpx.Response(
                    201,
                    json={
                        "token": "telegram-token",
                        "trackedUrl": "https://trk.dilim.net/go/telegram-token",
                        "reused": False,
                    },
                )
            )
            await publisher.publish_one(qi, deal)

        db_session.refresh(qi)
        assert qi.status == "published"
        assert qi.message_id == 99999
        assert qi.published_at is not None
        tracked_link = publisher._telegram.send_deal.await_args.kwargs["link"]
        assert tracked_link == "https://trk.dilim.net/go/telegram-token"

    async def test_publish_whatsapp_item_marks_published(self, publisher: DealPublisher, db_session):
        deal, qi = _seed_deal(db_session, deal_id=2, platform="whatsapp", target_ref="120@g.us")

        with respx.mock:
            respx.post("https://trk.dilim.net/api/tracking-links").mock(
                return_value=httpx.Response(
                    201,
                    json={
                        "token": "wa-token",
                        "trackedUrl": "https://trk.dilim.net/go/wa-token",
                        "reused": False,
                    },
                )
            )
            await publisher.publish_one(qi, deal)

        db_session.refresh(qi)
        assert qi.status == "published"
        assert qi.message_id is None
        publisher._whatsapp.send_deal.assert_awaited_once()
        sent_text = publisher._whatsapp.send_deal.await_args.kwargs["text"]
        assert "https://trk.dilim.net/go/wa-token" in sent_text

    async def test_publish_facebook_item_marks_published(self, publisher: DealPublisher, db_session):
        deal, qi = _seed_deal(
            db_session,
            deal_id=3,
            platform="facebook",
            target_ref="https://www.facebook.com/groups/test",
        )

        with respx.mock:
            respx.post("https://trk.dilim.net/api/tracking-links").mock(
                return_value=httpx.Response(
                    201,
                    json={
                        "token": "fb-token",
                        "trackedUrl": "https://trk.dilim.net/go/fb-token",
                        "reused": False,
                    },
                )
            )
            await publisher.publish_one(qi, deal)

        db_session.refresh(qi)
        assert qi.status == "published"
        assert qi.message_id is None
        publisher._facebook.send_deal.assert_awaited_once()
        assert publisher._facebook.send_deal.await_args.kwargs["purchase_url"] == (
            "https://trk.dilim.net/go/fb-token"
        )

    async def test_check_queue_processes_one_item_per_lane(self, publisher: DealPublisher, db_session):
        main_deal, main_qi = _seed_deal(db_session, deal_id=40, platform="telegram", target_ref="@main")
        category_deal, category_qi = _seed_deal(
            db_session,
            deal_id=41,
            platform="whatsapp",
            target_ref="120@g.us",
        )
        main_qi.destination_key = "tg_main"
        category_qi.destination_key = "wa_tech"
        main_qi.priority = 80
        category_qi.priority = 75
        db_session.commit()
        publisher.is_quiet_hour = MagicMock(return_value=False)

        with respx.mock:
            route = respx.post("https://trk.dilim.net/api/tracking-links").mock(
                side_effect=[
                    httpx.Response(
                        201,
                        json={
                            "token": "main-token",
                            "trackedUrl": "https://trk.dilim.net/go/main-token",
                            "reused": False,
                        },
                    ),
                    httpx.Response(
                        201,
                        json={
                            "token": "category-token",
                            "trackedUrl": "https://trk.dilim.net/go/category-token",
                            "reused": False,
                        },
                    ),
                ]
            )
            await publisher.check_queue()

        db_session.refresh(main_qi)
        db_session.refresh(category_qi)
        assert main_qi.status == "published"
        assert category_qi.status == "published"
        assert route.call_count == 2
        publisher._telegram.send_deal.assert_awaited()
        publisher._whatsapp.send_deal.assert_awaited()

    async def test_check_queue_skips_rate_limited_candidate_and_publishes_next_main_item(
        self, publisher: DealPublisher, db_session
    ):
        _, slow_published = _seed_deal(
            db_session,
            deal_id=50,
            platform="facebook",
            target_ref="https://www.facebook.com/groups/deals20",
        )
        slow_published.destination_key = "fb_beer_sheva_together"
        slow_published.status = "published"
        slow_published.published_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=30)

        _, slow_queued = _seed_deal(
            db_session,
            deal_id=51,
            platform="facebook",
            target_ref="https://www.facebook.com/groups/deals20",
        )
        slow_queued.destination_key = "fb_beer_sheva_together"
        slow_queued.priority = 95

        _, tg_main = _seed_deal(db_session, deal_id=52, platform="telegram", target_ref="@main")
        tg_main.destination_key = "tg_main"
        tg_main.priority = 80
        db_session.commit()
        publisher.is_quiet_hour = MagicMock(return_value=False)

        with respx.mock:
            respx.post("https://trk.dilim.net/api/tracking-links").mock(
                return_value=httpx.Response(
                    201,
                    json={
                        "token": "tg-main-token",
                        "trackedUrl": "https://trk.dilim.net/go/tg-main-token",
                        "reused": False,
                    },
                )
            )
            await publisher.check_queue()

        db_session.refresh(slow_queued)
        db_session.refresh(tg_main)
        assert slow_queued.status == "queued"
        assert tg_main.status == "published"
        publisher._telegram.send_deal.assert_awaited()
