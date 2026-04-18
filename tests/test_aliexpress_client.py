from types import SimpleNamespace

from bot.aliexpress_client import AliExpressClient, extract_promo_codes, select_best_sale_price


def test_catalog_client_can_be_enabled_without_tracking_id():
    client = AliExpressClient(
        app_key="key",
        app_secret="secret",
        tracking_id="",
        account_key="catalog",
        require_tracking_id=False,
    )

    assert client.is_enabled is True


def test_extract_promo_codes_from_api_payload():
    raw = [
        SimpleNamespace(
            promo_code="SAVE7",
            code_value="On order over USD 10, get USD 7 off",
            code_mini_spend="10",
            code_promotionurl="https://example.com/promo",
        ),
        SimpleNamespace(
            promo_code="SAVE7",
            code_value="duplicate",
        ),
    ]

    promo_codes = extract_promo_codes(raw)

    assert len(promo_codes) == 1
    assert promo_codes[0].code == "SAVE7"
    assert promo_codes[0].value == "On order over USD 10, get USD 7 off"
    assert promo_codes[0].minimum_spend == "10"


def test_select_best_sale_price_prefers_lower_app_price():
    assert select_best_sale_price(38.6, 30.94) == 30.94
    assert select_best_sale_price(38.6, None) == 38.6


def test_get_orders_parses_affiliate_orders():
    client = AliExpressClient(
        app_key="key",
        app_secret="secret",
        tracking_id="track",
    )
    client._api = SimpleNamespace(
        get_order_list=lambda **kwargs: SimpleNamespace(
            total_page_no=2,
            orders=SimpleNamespace(
                order=[
                    SimpleNamespace(
                        order_id="1001",
                        sub_order_id="1001-1",
                        order_status="Payment Completed",
                        tracking_id="track",
                        custom_parameters='{"token":"abc"}',
                        product_id="2002",
                        product_title="Order Product",
                        product_detail_url="https://www.aliexpress.com/item/2002.html",
                        product_main_image_url="https://img.example/2002.jpg",
                        product_count="1",
                        ship_to_country="IL",
                        settled_currency="USD",
                        paid_amount="12.3",
                        finished_amount="10.5",
                        estimated_paid_commission="1.1",
                        estimated_finished_commission="0.9",
                        commission_rate="7%",
                        incentive_commission_rate="1%",
                        new_buyer_bonus_commission="0.2",
                        is_new_buyer="Y",
                        order_type="global",
                        order_platform="pc",
                        effect_detail_status="valid",
                        category_id="123",
                        created_time="2026-04-18 12:00:00",
                        paid_time="2026-04-18 12:05:00",
                        finished_time="2026-04-20 12:05:00",
                        completed_settlement_time="2026-04-25 12:05:00",
                    )
                ]
            ),
        )
    )

    orders, total_pages = client.get_orders(
        status="Payment Completed",
        start_time="2026-04-01 00:00:00",
        end_time="2026-04-18 23:59:59",
    )

    assert total_pages == 2
    assert len(orders) == 1
    assert orders[0].order_id == "1001"
    assert orders[0].product_id == "2002"
    assert orders[0].commission_rate == 7.0
    assert orders[0].is_new_buyer is True


def test_get_orders_returns_empty_when_api_reports_no_orders():
    client = AliExpressClient(
        app_key="key",
        app_secret="secret",
        tracking_id="track",
    )
    client._api = SimpleNamespace(
        get_order_list=lambda **kwargs: (_ for _ in ()).throw(Exception("No orders found"))
    )

    orders, total_pages = client.get_orders(
        status="Payment Completed",
        start_time="2026-04-01 00:00:00",
        end_time="2026-04-18 23:59:59",
    )

    assert orders == []
    assert total_pages == 0
