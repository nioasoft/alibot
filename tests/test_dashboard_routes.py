import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from bot.config import DestinationConfig
from bot.models import AffiliateClickEvent, AffiliateLinkToken, Deal, init_db
from dashboard.app import create_dashboard
from bot.models import PublishQueueItem
from dashboard.routes import _build_queue_item_view, _status_summary


def _queue_item(status: str) -> PublishQueueItem:
    now = datetime.datetime.now(datetime.UTC)
    return PublishQueueItem(
        deal_id=1,
        target_group="legacy",
        destination_key=f"{status}-dest",
        platform="telegram",
        target_ref="@target",
        status=status,
        priority=0,
        scheduled_after=now,
        published_at=None,
        message_id=None,
        error_message=None,
    )


def test_status_summary_compacts_multiple_queue_items() -> None:
    summary = _status_summary(
        [
            _queue_item("published"),
            _queue_item("queued"),
            _queue_item("queued"),
        ]
    )

    assert summary == {
        "label": "✅ 1 פורסם · ⏳ 2 בתור",
        "class_name": "text-blue-600",
    }


def test_status_summary_handles_empty_queue() -> None:
    assert _status_summary([]) == {
        "label": "—",
        "class_name": "text-gray-400",
    }


def test_build_queue_item_view_formats_destination_metadata() -> None:
    now = datetime.datetime.now(datetime.UTC)
    queue_item = PublishQueueItem(
        deal_id=1,
        target_group="legacy",
        destination_key="fb_main",
        platform="facebook",
        target_ref="https://www.facebook.com/groups/354824431284295",
        status="published",
        priority=0,
        scheduled_after=now,
        published_at=now,
        message_id=None,
        error_message=None,
    )
    destinations = {
        "fb_main": DestinationConfig(
            key="fb_main",
            enabled=True,
            platform="facebook",
            target="https://www.facebook.com/groups/354824431284295",
            categories=["*"],
        )
    }

    view = _build_queue_item_view(queue_item, destinations)

    assert view["platform_label"] == "פייסבוק"
    assert view["destination_name"] == "קבוצת פייסבוק ראשית"
    assert view["target_display"] == "www.facebook.com/groups/354824431284295"
    assert view["status_label"] == "פורסם"


def test_deals_page_renders_with_status_filter(tmp_path) -> None:
    db_path = tmp_path / "dashboard.db"
    session_factory = init_db(str(db_path))
    app = create_dashboard(
        session_factory,
        SimpleNamespace(
            dashboard=SimpleNamespace(auto_refresh_seconds=30),
            publishing=SimpleNamespace(destinations={}),
            tracking=SimpleNamespace(base_url="https://trk.dilim.net"),
        ),
    )

    now = datetime.datetime.now(datetime.UTC)
    with session_factory() as session:
        session.add(
            Deal(
                raw_message_id=1,
                product_id="product-1",
                product_name="Sample deal",
                original_text="original",
                rewritten_text="rewritten",
                price=9.99,
                original_price=None,
                currency="USD",
                shipping=None,
                category="tech",
                ali_category_raw=None,
                category_source=None,
                affiliate_account_key=None,
                affiliate_link=None,
                product_link="https://example.com/product",
                image_hash=None,
                image_path=None,
                text_hash="hash-1",
                source_group="@source",
                created_at=now,
            )
        )
        session.commit()

    client = TestClient(app)

    assert client.get("/deals").status_code == 200
    assert client.get("/deals?status=published").status_code == 200
    assert client.get("/queue").status_code == 200
    assert client.get("/").status_code == 200


def test_tracking_redirect_logs_click_and_redirects(tmp_path) -> None:
    db_path = tmp_path / "tracking.db"
    session_factory = init_db(str(db_path))
    app = create_dashboard(
        session_factory,
        SimpleNamespace(
            dashboard=SimpleNamespace(auto_refresh_seconds=30),
            publishing=SimpleNamespace(destinations={}),
            tracking=SimpleNamespace(base_url="https://trk.dilim.net"),
        ),
    )

    now = datetime.datetime.now(datetime.UTC)
    with session_factory() as session:
        deal = Deal(
            raw_message_id=1,
            product_id="product-2",
            product_name="Tracked deal",
            original_text="original",
            rewritten_text="rewritten",
            price=19.99,
            original_price=None,
            currency="USD",
            shipping=None,
            category="tech",
            ali_category_raw=None,
            category_source=None,
            affiliate_account_key="primary",
            affiliate_link="https://s.click.aliexpress.com/e/_tracked",
            product_link="https://example.com/product",
            image_hash=None,
            image_path=None,
            text_hash="hash-2",
            source_group="@source",
            created_at=now,
        )
        session.add(deal)
        session.flush()

        queue_item = PublishQueueItem(
            deal_id=deal.id,
            target_group="legacy",
            destination_key="tg_main",
            platform="telegram",
            target_ref="@target",
            status="published",
            priority=0,
            scheduled_after=now,
            published_at=now,
            message_id=123,
            error_message=None,
        )
        session.add(queue_item)
        session.flush()

        token = AffiliateLinkToken(
            token="abc123",
            deal_id=deal.id,
            queue_item_id=queue_item.id,
            destination_key="tg_main",
            platform="telegram",
            source_group="@source",
            affiliate_account_key="primary",
            tracking_id=None,
            custom_parameters=None,
            target_url="https://s.click.aliexpress.com/e/_tracked",
            created_at=now,
        )
        session.add(token)
        session.commit()

    client = TestClient(app)
    response = client.get(
        "/go/abc123",
        follow_redirects=False,
        headers={
            "user-agent": "pytest-agent",
            "referer": "https://t.me/test",
            "x-forwarded-for": "1.2.3.4",
        },
    )

    assert response.status_code == 302
    assert response.headers["location"] == "https://s.click.aliexpress.com/e/_tracked"

    with session_factory() as session:
        clicks = session.query(AffiliateClickEvent).all()
        assert len(clicks) == 1
        assert clicks[0].platform == "telegram"
        assert clicks[0].destination_key == "tg_main"
        assert clicks[0].user_agent == "pytest-agent"
        assert clicks[0].referer == "https://t.me/test"


def test_tracking_redirect_returns_404_for_unknown_token(tmp_path) -> None:
    db_path = tmp_path / "tracking-miss.db"
    session_factory = init_db(str(db_path))
    app = create_dashboard(
        session_factory,
        SimpleNamespace(
            dashboard=SimpleNamespace(auto_refresh_seconds=30),
            publishing=SimpleNamespace(destinations={}),
            tracking=SimpleNamespace(base_url="https://trk.dilim.net"),
        ),
    )
    client = TestClient(app)

    response = client.get("/go/missing-token", follow_redirects=False)

    assert response.status_code == 404
