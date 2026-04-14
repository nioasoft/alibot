"""Tests for the HotProductFetcher module."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image
from sqlalchemy import select

from bot.category_resolver import CategoryResolution
from bot.hot_products import HotProductFetcher, _download_image
from bot.models import Deal, PublishQueueItem, RawMessage
from bot.quality import QualityDecision
from bot.rewriter import ContentRewriter, RewriteResult


def _make_logo_image() -> bytes:
    img = Image.new("RGBA", (50, 50), (255, 0, 0, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_test_image() -> bytes:
    img = Image.new("RGB", (200, 200), (0, 128, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_product(
    product_id: str = "12345",
    title: str = "Test Earbuds",
    sale_price: float = 9.99,
    original_price: float = 19.99,
    promo_link: str = "https://s.click.aliexpress.com/test",
    image_url: str = "https://ae01.alicdn.com/test.jpg",
    category: str = "Consumer Electronics",
    orders: int = 500,
    discount: str = "50%",
    app_sale_price: float | None = None,
    promo_code_info=None,
) -> MagicMock:
    p = MagicMock()
    p.product_id = product_id
    p.product_title = title
    p.target_sale_price = sale_price
    p.target_app_sale_price = app_sale_price if app_sale_price is not None else sale_price
    p.target_original_price = original_price
    p.promotion_link = promo_link
    p.product_main_image_url = image_url
    p.first_level_category_name = category
    p.lastest_volume = orders
    p.discount = discount
    p.promo_code_info = promo_code_info
    return p


@pytest.fixture
def mock_ali_api() -> MagicMock:
    api = MagicMock()
    api.is_enabled = True
    return api


@pytest.fixture
def mock_rewriter() -> MagicMock:
    rw = MagicMock()
    rw.rewrite = AsyncMock(
        return_value=RewriteResult(
            rewritten_text="🔥 אוזניות בלוטוס מהממות!",
            category="tech",
            product_name_clean="Bluetooth Earbuds",
        )
    )
    helper = ContentRewriter(api_key="sk-test", model="gpt-4o-mini")
    rw.finalize_text = helper.finalize_text
    return rw


@pytest.fixture
def mock_image_processor(tmp_path) -> MagicMock:
    logo_path = tmp_path / "logo.png"
    logo_path.write_bytes(_make_logo_image())

    from bot.image_processor import ImageProcessor

    return ImageProcessor(logo_path=str(logo_path))


@pytest.fixture
def fetcher(mock_ali_api, mock_rewriter, mock_image_processor, db_session, tmp_path) -> HotProductFetcher:
    router = MagicMock()
    router.resolve.return_value = [
        MagicMock(key="tg_tech", platform="telegram", target="@tech_channel"),
        MagicMock(key="wa_tech", platform="whatsapp", target="120@g.us"),
    ]

    category_resolver = MagicMock()
    category_resolver.resolve = AsyncMock(
        return_value=CategoryResolution(
            category="tech",
            source="api",
            ali_category_raw="Consumer Electronics",
        )
    )

    affiliate_pool = MagicMock()
    affiliate_pool.get_affiliate_link.return_value = ("https://aff.link", "secondary")

    quality_gate = MagicMock()
    quality_gate.evaluate_hot_product.return_value = QualityDecision(
        accepted=True,
        score=88,
        priority=88,
        reason="quality_pass",
    )
    quality_gate.idle_destination_hours = 6

    return HotProductFetcher(
        ali_api=mock_ali_api,
        rewriter=mock_rewriter,
        image_processor=mock_image_processor,
        session=db_session,
        router=router,
        category_resolver=category_resolver,
        affiliate_pool=affiliate_pool,
        max_products_per_run=3,
        quality_gate=quality_gate,
    )


@pytest.mark.asyncio
class TestFetchAndQueue:
    async def test_returns_zero_when_api_disabled(self, fetcher: HotProductFetcher, mock_ali_api: MagicMock):
        mock_ali_api.is_enabled = False
        assert await fetcher.fetch_and_queue() == 0

    async def test_queues_products_up_to_max(
        self,
        fetcher: HotProductFetcher,
        mock_ali_api: MagicMock,
        db_session,
        tmp_path,
    ):
        mock_ali_api.search_products.return_value = [_make_product(product_id=str(i)) for i in range(10)]

        with patch("bot.hot_products._download_image", return_value=_make_test_image()), patch(
            "bot.hot_products._IMAGE_DIR", tmp_path
        ):
            result = await fetcher.fetch_and_queue()

        assert result == 3
        assert len(db_session.execute(select(Deal)).scalars().all()) == 3
        assert len(db_session.execute(select(PublishQueueItem)).scalars().all()) == 6


@pytest.mark.asyncio
class TestProcessProduct:
    async def test_creates_deal_with_correct_fields(self, fetcher: HotProductFetcher, db_session, tmp_path):
        product = _make_product(product_id="TEST001", title="Super Earbuds")

        with patch("bot.hot_products._download_image", return_value=_make_test_image()), patch(
            "bot.hot_products._IMAGE_DIR", tmp_path
        ):
            deal = await fetcher._process_product(product)

        assert deal is not None
        assert deal.product_id == "TEST001"
        assert deal.category == "tech"
        assert deal.ali_category_raw == "Consumer Electronics"
        assert deal.affiliate_account_key == "secondary"
        assert deal.affiliate_link == "https://aff.link"

        queue_items = db_session.execute(select(PublishQueueItem)).scalars().all()
        assert len(queue_items) == 2
        assert {item.platform for item in queue_items} == {"telegram", "whatsapp"}
        assert {item.priority for item in queue_items} == {88}

    async def test_falls_back_to_search_promo_link_when_pool_returns_none(
        self, fetcher: HotProductFetcher, db_session, tmp_path
    ):
        fetcher._affiliate_pool.get_affiliate_link.return_value = (None, None)
        product = _make_product(promo_link="https://fallback.link")

        with patch("bot.hot_products._download_image", return_value=None), patch(
            "bot.hot_products._IMAGE_DIR", tmp_path
        ):
            deal = await fetcher._process_product(product)

        assert deal is not None
        assert deal.affiliate_link == "https://fallback.link"
        raw = db_session.execute(select(RawMessage)).scalar_one()
        assert raw.source_group == "hot_products"

    async def test_skips_low_quality_product(self, fetcher: HotProductFetcher, db_session, tmp_path):
        fetcher._quality_gate.evaluate_hot_product.return_value = QualityDecision(
            accepted=False,
            score=25,
            priority=25,
            reason="quality_below_threshold",
        )
        product = _make_product(product_id="LOW001")

        with patch("bot.hot_products._download_image", return_value=_make_test_image()), patch(
            "bot.hot_products._IMAGE_DIR", tmp_path
        ):
            deal = await fetcher._process_product(product)

        assert deal is None
        assert db_session.execute(select(Deal)).scalars().all() == []

    async def test_idle_destination_override_allows_low_quality_product(
        self, fetcher: HotProductFetcher, db_session, tmp_path
    ):
        fetcher._quality_gate.evaluate_hot_product.return_value = QualityDecision(
            accepted=True,
            score=25,
            priority=175,
            reason="idle_destination_override",
        )
        product = _make_product(product_id="IDLE001")

        with patch("bot.hot_products._download_image", return_value=_make_test_image()), patch(
            "bot.hot_products._IMAGE_DIR", tmp_path
        ):
            deal = await fetcher._process_product(product)

        assert deal is not None
        queue_items = db_session.execute(select(PublishQueueItem)).scalars().all()
        assert {item.priority for item in queue_items} == {175}

    async def test_hot_product_uses_app_price_and_api_coupon_codes(
        self, fetcher: HotProductFetcher, db_session, tmp_path
    ):
        promo = MagicMock()
        promo.promo_code = "SAVE7"
        promo.code_value = "On order over USD 10, get USD 7 off"
        product = _make_product(
            product_id="PROMO001",
            sale_price=38.6,
            app_sale_price=30.94,
            promo_code_info=promo,
        )

        with patch("bot.hot_products._download_image", return_value=_make_test_image()), patch(
            "bot.hot_products._IMAGE_DIR", tmp_path
        ):
            deal = await fetcher._process_product(product)

        assert deal is not None
        assert deal.price == 30.94
        assert "🎟️ קוד הנחה: SAVE7 - On order over USD 10, get USD 7 off" in deal.rewritten_text


class TestDownloadImage:
    def test_returns_bytes_on_success(self):
        mock_response = MagicMock()
        mock_response.content = b"img"
        mock_response.raise_for_status = MagicMock()

        with patch("bot.hot_products.httpx.get", return_value=mock_response):
            assert _download_image("https://example.com/image.jpg") == b"img"

    def test_returns_none_on_http_error(self):
        import httpx

        with patch("bot.hot_products.httpx.get", side_effect=httpx.HTTPError("timeout")):
            assert _download_image("https://example.com/image.jpg") is None
