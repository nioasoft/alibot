"""Tests for SupabasePublisher."""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bot.supabase_publisher import SupabasePublisher


def _make_deal(
    product_id: str = "12345",
    product_name: str = "Test Product",
    price: float = 9.99,
    original_price: float | None = 19.99,
    currency: str = "USD",
    category: str = "tech",
    image_path: str | None = None,
) -> MagicMock:
    deal = MagicMock()
    deal.product_id = product_id
    deal.product_name = product_name
    deal.rewritten_text = "מוצר מעולה במחיר שווה!"
    deal.price = price
    deal.original_price = original_price
    deal.currency = currency
    deal.category = category
    deal.affiliate_link = "https://s.click.aliexpress.com/e/abc123"
    deal.product_link = "https://aliexpress.com/item/12345.html"
    deal.image_path = image_path
    deal.created_at = datetime.datetime.now(datetime.UTC)
    return deal


@pytest.fixture
def mock_supabase():
    with patch("supabase.create_client") as mock_create:
        client = MagicMock()
        mock_create.return_value = client
        yield client


@pytest.fixture
def publisher(mock_supabase):
    return SupabasePublisher(url="https://test.supabase.co", key="test-key")


class TestSupabasePublisher:
    def test_is_enabled(self, publisher):
        assert publisher.is_enabled is True

    @pytest.mark.asyncio
    async def test_send_deal_without_image(self, publisher, mock_supabase):
        deal = _make_deal()

        result = await publisher.send_deal("default-feed", deal)

        assert result is True
        mock_supabase.table.assert_called_with("deals")
        upsert_call = mock_supabase.table().upsert
        upsert_call.assert_called_once()
        row = upsert_call.call_args[0][0]
        assert row["product_id"] == "12345"
        assert row["product_name"] == "Test Product"
        assert row["category"] == "tech"
        assert row["image_url"] is None
        assert row["is_active"] is True

    @pytest.mark.asyncio
    async def test_send_deal_with_image(self, publisher, mock_supabase, tmp_path):
        image_file = tmp_path / "test.jpg"
        image_file.write_bytes(b"\xff\xd8\xff\xe0test-image-data")
        deal = _make_deal(image_path=str(image_file))

        mock_supabase.storage.from_().get_public_url.return_value = (
            "https://test.supabase.co/storage/v1/object/public/deal-images/12345.jpg"
        )

        result = await publisher.send_deal("default-feed", deal)

        assert result is True
        mock_supabase.storage.from_().upload.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_deal_missing_image_file(self, publisher, mock_supabase):
        deal = _make_deal(image_path="/nonexistent/path.jpg")

        result = await publisher.send_deal("default-feed", deal)

        assert result is True
        row = mock_supabase.table().upsert.call_args[0][0]
        assert row["image_url"] is None

    @pytest.mark.asyncio
    async def test_send_deal_ils_price(self, publisher, mock_supabase):
        deal = _make_deal(currency="ILS", price=35.0)

        result = await publisher.send_deal("default-feed", deal)

        assert result is True
        row = mock_supabase.table().upsert.call_args[0][0]
        assert row["price_ils"] == 35.0

    @pytest.mark.asyncio
    @patch("bot.exchange_rate.get_cached_rate", return_value=3.6)
    async def test_send_deal_usd_to_ils_conversion(self, mock_rate, publisher, mock_supabase):
        deal = _make_deal(currency="USD", price=10.0)

        result = await publisher.send_deal("default-feed", deal)

        assert result is True
        row = mock_supabase.table().upsert.call_args[0][0]
        assert row["price_ils"] == 36.0

    @pytest.mark.asyncio
    async def test_send_deal_upsert_on_conflict(self, publisher, mock_supabase):
        deal = _make_deal()

        await publisher.send_deal("default-feed", deal)

        mock_supabase.table().upsert.assert_called_once()
        kwargs = mock_supabase.table().upsert.call_args[1]
        assert kwargs["on_conflict"] == "product_id"

    @pytest.mark.asyncio
    async def test_send_deal_exception_returns_false(self, publisher, mock_supabase):
        mock_supabase.table.side_effect = Exception("Connection error")
        deal = _make_deal()

        result = await publisher.send_deal("default-feed", deal)

        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_old_images(self, publisher, mock_supabase):
        mock_supabase.table().select().lt().execute.return_value = MagicMock(
            data=[
                {"product_id": "old1"},
                {"product_id": "old2"},
            ]
        )

        await publisher.cleanup_old_images(days=7)

        mock_supabase.storage.from_().remove.assert_called_once_with(
            ["old1.jpg", "old2.jpg"]
        )

    @pytest.mark.asyncio
    async def test_cleanup_no_old_images(self, publisher, mock_supabase):
        mock_supabase.table().select().lt().execute.return_value = MagicMock(data=[])

        await publisher.cleanup_old_images(days=7)

        mock_supabase.storage.from_().remove.assert_not_called()
