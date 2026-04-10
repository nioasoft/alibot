"""Tests for the HotProductFetcher module."""

from __future__ import annotations

import io
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image
from sqlalchemy import select

from bot.hot_products import HotProductFetcher, _download_image
from bot.models import Deal, PublishQueueItem, RawMessage
from bot.rewriter import RewriteResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    commission: str = "7.0%",
    discount: str = "50%",
) -> MagicMock:
    p = MagicMock()
    p.product_id = product_id
    p.product_title = title
    p.target_sale_price = sale_price
    p.target_original_price = original_price
    p.promotion_link = promo_link
    p.product_main_image_url = image_url
    p.first_level_category_name = category
    p.lastest_volume = orders
    p.commission_rate = commission
    p.discount = discount
    return p


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
    return rw


@pytest.fixture
def mock_image_processor(tmp_path) -> MagicMock:
    logo_path = tmp_path / "logo.png"
    logo_path.write_bytes(_make_logo_image())

    from bot.image_processor import ImageProcessor

    return ImageProcessor(logo_path=str(logo_path))


@pytest.fixture
def fetcher(mock_ali_api, mock_rewriter, mock_image_processor, db_session, tmp_path) -> HotProductFetcher:
    return HotProductFetcher(
        ali_api=mock_ali_api,
        rewriter=mock_rewriter,
        image_processor=mock_image_processor,
        session=db_session,
        target_groups={"tech": "@tech_channel", "default": "@main_channel"},
        channel_link="https://t.me/test",
        max_products_per_run=3,
    )


# ---------------------------------------------------------------------------
# Tests: HotProductFetcher.fetch_and_queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFetchAndQueue:
    async def test_returns_zero_when_api_disabled(
        self, fetcher: HotProductFetcher, mock_ali_api: MagicMock
    ):
        mock_ali_api.is_enabled = False

        result = await fetcher.fetch_and_queue()

        assert result == 0
        mock_ali_api.search_products.assert_not_called()

    async def test_returns_zero_on_empty_results(
        self, fetcher: HotProductFetcher, mock_ali_api: MagicMock
    ):
        mock_ali_api.search_products.return_value = []

        result = await fetcher.fetch_and_queue()

        assert result == 0

    async def test_returns_zero_on_api_exception(
        self, fetcher: HotProductFetcher, mock_ali_api: MagicMock
    ):
        mock_ali_api.search_products.side_effect = RuntimeError("API error")

        result = await fetcher.fetch_and_queue()

        assert result == 0

    async def test_queues_products_up_to_max(
        self,
        fetcher: HotProductFetcher,
        mock_ali_api: MagicMock,
        db_session,
        tmp_path,
    ):
        products = [_make_product(product_id=str(i)) for i in range(10)]
        mock_ali_api.search_products.return_value = products

        with patch("bot.hot_products._download_image", return_value=_make_test_image()), \
             patch("bot.hot_products._IMAGE_DIR", tmp_path):
            result = await fetcher.fetch_and_queue()

        assert result == 3  # max_products_per_run

        deals = db_session.execute(select(Deal)).scalars().all()
        assert len(deals) == 3

        queue_items = db_session.execute(select(PublishQueueItem)).scalars().all()
        assert len(queue_items) == 3

    async def test_skips_already_existing_product(
        self,
        fetcher: HotProductFetcher,
        mock_ali_api: MagicMock,
        db_session,
        tmp_path,
    ):
        product = _make_product(product_id="existing_id")
        mock_ali_api.search_products.return_value = [product]

        with patch("bot.hot_products._download_image", return_value=_make_test_image()), \
             patch("bot.hot_products._IMAGE_DIR", tmp_path):
            # First run creates it
            await fetcher.fetch_and_queue()
            initial_count = len(db_session.execute(select(Deal)).scalars().all())

            # Second run should skip it
            result = await fetcher.fetch_and_queue()

        assert result == 0
        final_count = len(db_session.execute(select(Deal)).scalars().all())
        assert final_count == initial_count

    async def test_skips_product_without_promo_link(
        self,
        fetcher: HotProductFetcher,
        mock_ali_api: MagicMock,
        db_session,
    ):
        product = _make_product(promo_link="")
        mock_ali_api.search_products.return_value = [product]

        result = await fetcher.fetch_and_queue()

        assert result == 0
        assert db_session.execute(select(Deal)).scalars().first() is None


# ---------------------------------------------------------------------------
# Tests: _process_product
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestProcessProduct:
    async def test_creates_deal_with_correct_fields(
        self,
        fetcher: HotProductFetcher,
        db_session,
        tmp_path,
    ):
        product = _make_product(
            product_id="TEST001",
            title="Super Earbuds",
            sale_price=9.99,
            original_price=19.99,
            category="Consumer Electronics",
        )

        with patch("bot.hot_products._download_image", return_value=_make_test_image()), \
             patch("bot.hot_products._IMAGE_DIR", tmp_path):
            deal = await fetcher._process_product(product)

        assert deal is not None
        assert deal.product_id == "TEST001"
        assert deal.price == 9.99
        assert deal.original_price == 19.99
        assert deal.currency == "USD"
        assert deal.category == "tech"  # mapped from "Consumer Electronics"
        assert deal.source_group == "hot_products"
        assert deal.affiliate_link == "https://s.click.aliexpress.com/test"

    async def test_creates_raw_message_for_traceability(
        self,
        fetcher: HotProductFetcher,
        db_session,
        tmp_path,
    ):
        product = _make_product()

        with patch("bot.hot_products._download_image", return_value=_make_test_image()), \
             patch("bot.hot_products._IMAGE_DIR", tmp_path):
            await fetcher._process_product(product)

        raw = db_session.execute(select(RawMessage)).scalar_one()
        assert raw.source_group == "hot_products"
        assert raw.status == "processed"
        assert raw.telegram_message_id == 0

    async def test_creates_queue_item_targeting_correct_group(
        self,
        fetcher: HotProductFetcher,
        db_session,
        tmp_path,
    ):
        product = _make_product(category="Consumer Electronics")

        with patch("bot.hot_products._download_image", return_value=_make_test_image()), \
             patch("bot.hot_products._IMAGE_DIR", tmp_path):
            await fetcher._process_product(product)

        queue_item = db_session.execute(select(PublishQueueItem)).scalar_one()
        assert queue_item.status == "queued"
        assert queue_item.target_group == "@tech_channel"

    async def test_falls_back_to_default_group_for_unknown_category(
        self,
        fetcher: HotProductFetcher,
        db_session,
        mock_rewriter: MagicMock,
        tmp_path,
    ):
        # Rewriter returns unknown category
        mock_rewriter.rewrite = AsyncMock(
            return_value=RewriteResult(
                rewritten_text="מוצר מעולה",
                category="unknown_cat",
                product_name_clean="Some Product",
            )
        )
        product = _make_product(category="Unknown AliExpress Category")

        with patch("bot.hot_products._download_image", return_value=_make_test_image()), \
             patch("bot.hot_products._IMAGE_DIR", tmp_path):
            await fetcher._process_product(product)

        queue_item = db_session.execute(select(PublishQueueItem)).scalar_one()
        assert queue_item.target_group == "@main_channel"

    async def test_handles_image_download_failure_gracefully(
        self,
        fetcher: HotProductFetcher,
        db_session,
        tmp_path,
    ):
        product = _make_product()

        with patch("bot.hot_products._download_image", return_value=None), \
             patch("bot.hot_products._IMAGE_DIR", tmp_path):
            deal = await fetcher._process_product(product)

        assert deal is not None
        assert deal.image_path is None
        assert deal.image_hash is None

    async def test_original_price_set_to_none_when_not_discounted(
        self,
        fetcher: HotProductFetcher,
        db_session,
        tmp_path,
    ):
        # original_price == sale_price (no discount)
        product = _make_product(sale_price=10.0, original_price=10.0)

        with patch("bot.hot_products._download_image", return_value=None), \
             patch("bot.hot_products._IMAGE_DIR", tmp_path):
            deal = await fetcher._process_product(product)

        assert deal is not None
        assert deal.original_price is None

    async def test_returns_none_without_promo_link(
        self,
        fetcher: HotProductFetcher,
        db_session,
    ):
        product = _make_product(promo_link="")
        deal = await fetcher._process_product(product)
        assert deal is None


# ---------------------------------------------------------------------------
# Tests: _download_image helper
# ---------------------------------------------------------------------------


class TestDownloadImage:
    def test_returns_bytes_on_success(self):
        test_bytes = b"fake image content"
        mock_response = MagicMock()
        mock_response.content = test_bytes
        mock_response.raise_for_status = MagicMock()

        with patch("bot.hot_products.httpx.get", return_value=mock_response):
            result = _download_image("https://example.com/image.jpg")

        assert result == test_bytes

    def test_returns_none_on_http_error(self):
        import httpx

        with patch("bot.hot_products.httpx.get", side_effect=httpx.HTTPError("timeout")):
            result = _download_image("https://example.com/image.jpg")

        assert result is None

    def test_returns_none_on_generic_exception(self):
        with patch("bot.hot_products.httpx.get", side_effect=Exception("unexpected")):
            result = _download_image("https://example.com/image.jpg")

        assert result is None


# ---------------------------------------------------------------------------
# Tests: Category mapping
# ---------------------------------------------------------------------------


class TestCategoryMapping:
    @pytest.mark.parametrize(
        "ali_category,expected_internal",
        [
            ("Consumer Electronics", "tech"),
            ("Phones & Telecommunications", "tech"),
            ("Computer & Office", "tech"),
            ("Home & Garden", "home"),
            ("Home Improvement", "home"),
            ("Women's Clothing", "fashion"),
            ("Men's Clothing", "fashion"),
            ("Shoes", "fashion"),
            ("Jewelry & Accessories", "fashion"),
            ("Beauty & Health", "beauty"),
            ("Toys & Hobbies", "toys"),
            ("Sports & Entertainment", "sports"),
            ("Automobiles & Motorcycles", "auto"),
            ("Mother & Kids", "toys"),
        ],
    )
    def test_category_mapping(self, ali_category: str, expected_internal: str):
        from bot.hot_products import _CATEGORY_MAP

        assert _CATEGORY_MAP[ali_category] == expected_internal
