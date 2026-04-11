from unittest.mock import MagicMock

from bot.affiliate_pool import AffiliateLinkPool


def test_affiliate_pool_selects_weighted_account_and_returns_link():
    primary = MagicMock()
    primary.is_enabled = True
    primary.get_affiliate_link.return_value = "https://primary.link"

    secondary = MagicMock()
    secondary.is_enabled = True
    secondary.get_affiliate_link.return_value = "https://secondary.link"

    pool = AffiliateLinkPool(
        clients={"primary": primary, "secondary": secondary},
        distribution={"primary": 100, "secondary": 0},
    )

    link, key = pool.get_affiliate_link("https://www.aliexpress.com/item/1.html", seed="1")

    assert key == "primary"
    assert link == "https://primary.link"
