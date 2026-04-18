from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from bot.affiliate_order_sync import AffiliateOrderSync
from bot.aliexpress_client import AffiliateOrder


def _make_order(
    order_id: str = "1001",
    sub_order_id: str = "1001-1",
    product_id: str = "2002",
) -> AffiliateOrder:
    return AffiliateOrder(
        order_id=order_id,
        sub_order_id=sub_order_id,
        order_status="Payment Completed",
        tracking_id="track-main",
        custom_parameters='{"token":"abc"}',
        product_id=product_id,
        product_title="Sample Product",
        product_detail_url="https://www.aliexpress.com/item/2002.html",
        product_main_image_url="https://img.example/2002.jpg",
        product_count=1,
        ship_to_country="IL",
        settled_currency="USD",
        paid_amount=12.3,
        finished_amount=10.0,
        estimated_paid_commission=1.2,
        estimated_finished_commission=1.0,
        commission_rate=7.0,
        incentive_commission_rate=1.0,
        new_buyer_bonus_commission=0.2,
        is_new_buyer=True,
        order_type="global",
        order_platform="pc",
        effect_detail_status="valid",
        category_id=123,
        created_time="2026-04-18 12:00:00",
        paid_time="2026-04-18 12:05:00",
        finished_time="2026-04-20 12:05:00",
        completed_settlement_time="2026-04-25 12:05:00",
        raw_payload={"order_id": order_id},
    )


@pytest.fixture
def mock_supabase():
    with patch("bot.affiliate_order_sync.create_client") as mock_create:
        client = MagicMock()
        client.table().select().in_().execute.return_value = SimpleNamespace(
            data=[{"product_id": "2002", "category": "tech"}]
        )
        mock_create.return_value = client
        yield client


@pytest.mark.asyncio
async def test_sync_recent_orders_upserts_rows_with_resolved_category(mock_supabase):
    ali_client = MagicMock()
    ali_client.is_enabled = True
    ali_client.get_orders.side_effect = [
        ([_make_order()], 1),
        ([], 0),
    ]

    sync = AffiliateOrderSync(
        clients={"primary": ali_client},
        url="https://test.supabase.co",
        key="service-key",
        lookback_days=7,
    )

    result = await sync.sync_recent_orders()

    assert result["orders"] == 1
    mock_supabase.table.assert_any_call("affiliate_orders")
    upsert_args = mock_supabase.table().upsert.call_args[0][0]
    assert len(upsert_args) == 1
    assert upsert_args[0]["order_key"] == "primary:1001-1"
    assert upsert_args[0]["resolved_category"] == "tech"


@pytest.mark.asyncio
async def test_sync_recent_orders_returns_zero_when_no_enabled_clients(mock_supabase):
    disabled_client = MagicMock()
    disabled_client.is_enabled = False

    sync = AffiliateOrderSync(
        clients={"primary": disabled_client},
        url="https://test.supabase.co",
        key="service-key",
    )

    result = await sync.sync_recent_orders()

    assert result == {"orders": 0, "accounts": 0}
    mock_supabase.table().upsert.assert_not_called()
