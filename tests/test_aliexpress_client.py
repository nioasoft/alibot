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
