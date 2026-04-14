from unittest.mock import MagicMock

from bot.aliexpress_pool import AliExpressClientPool


def test_pool_falls_back_to_secondary_for_product_details():
    primary = MagicMock()
    primary.is_enabled = True
    primary.get_product_details.return_value = None

    secondary = MagicMock()
    secondary.is_enabled = True
    secondary.get_product_details.return_value = {"ok": True}

    pool = AliExpressClientPool(
        clients={"primary": primary, "secondary": secondary},
        preferred_key="primary",
    )

    result = pool.get_product_details("123")

    assert result == {"ok": True}
    primary.get_product_details.assert_called_once_with("123")
    secondary.get_product_details.assert_called_once_with("123")


def test_pool_returns_first_non_empty_search_results():
    primary = MagicMock()
    primary.is_enabled = True
    primary.search_products.return_value = []

    secondary = MagicMock()
    secondary.is_enabled = True
    secondary.search_products.return_value = ["product"]

    pool = AliExpressClientPool(
        clients={"primary": primary, "secondary": secondary},
        preferred_key="primary",
    )

    result = pool.search_products("usb cable")

    assert result == ["product"]
