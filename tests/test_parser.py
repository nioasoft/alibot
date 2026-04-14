import pytest
from bot.parser import DealParser, ParsedDeal


@pytest.fixture
def parser():
    return DealParser(
        min_message_length=20,
        supported_domains=["aliexpress.com", "s.click.aliexpress.com", "a.aliexpress.com"],
    )


class TestLinkExtraction:
    def test_extract_short_link(self, parser: DealParser):
        text = "Amazing deal! https://s.click.aliexpress.com/e/_oEhUSd4 only 29 ILS"
        result = parser.parse(text)
        assert result is not None
        assert result.link == "https://s.click.aliexpress.com/e/_oEhUSd4"

    def test_extract_direct_product_link(self, parser: DealParser):
        text = "Check this out https://www.aliexpress.com/item/1005003091506814.html great price"
        result = parser.parse(text)
        assert result is not None
        assert result.link == "https://www.aliexpress.com/item/1005003091506814.html"
        assert result.product_id == "1005003091506814"

    def test_extract_link_with_query_params(self, parser: DealParser):
        text = "Deal https://www.aliexpress.com/item/1005003091506814.html?spm=abc&algo=xyz only today"
        result = parser.parse(text)
        assert result is not None
        assert result.product_id == "1005003091506814"

    def test_no_aliexpress_link_returns_none(self, parser: DealParser):
        text = "This is a deal from Amazon https://amazon.com/dp/B09XYZ nice stuff"
        result = parser.parse(text)
        assert result is None

    def test_a_aliexpress_domain(self, parser: DealParser):
        text = "Great price https://a.aliexpress.com/_mK1abc2 go buy it"
        result = parser.parse(text)
        assert result is not None
        assert result.link == "https://a.aliexpress.com/_mK1abc2"

    def test_extracts_user_notes_without_link(self, parser: DealParser):
        text = (
            "אלה מכנסי ספורט https://www.aliexpress.com/item/1005003091506814.html "
            "אני רוצה שתכתוב שהם מתאימים לאימון וליום יום"
        )
        result = parser.parse(text)
        assert result is not None
        assert result.user_notes is not None
        assert "1005003091506814" not in result.user_notes
        assert "מתאימים לאימון" in result.user_notes

    def test_extracts_multiple_coupon_codes(self, parser: DealParser):
        text = (
            "דיל מטורף https://s.click.aliexpress.com/e/_abc123\n"
            "קוד הנחה: `ILAPR2` או `DSB2`"
        )
        result = parser.parse(text)
        assert result is not None
        assert result.coupon_codes == ["ILAPR2", "DSB2"]


class TestPriceExtraction:
    def test_extract_price_ils_symbol(self, parser: DealParser):
        text = "Wireless earbuds https://s.click.aliexpress.com/e/_abc only ₪45.90!"
        result = parser.parse(text)
        assert result is not None
        assert result.price == 45.90
        assert result.currency == "ILS"

    def test_extract_price_shekel_text(self, parser: DealParser):
        text = 'Gadget https://s.click.aliexpress.com/e/_abc 29 ש"ח with free shipping'
        result = parser.parse(text)
        assert result is not None
        assert result.price == 29.0
        assert result.currency == "ILS"

    def test_extract_price_usd(self, parser: DealParser):
        text = "Nice item https://s.click.aliexpress.com/e/_abc $12.99 shipped"
        result = parser.parse(text)
        assert result is not None
        assert result.price == 12.99
        assert result.currency == "USD"

    def test_extract_price_with_original(self, parser: DealParser):
        text = "Was ₪89 now ₪45! https://s.click.aliexpress.com/e/_abc huge discount"
        result = parser.parse(text)
        assert result is not None
        assert result.price == 45.0
        assert result.original_price == 89.0

    def test_no_price_still_parses(self, parser: DealParser):
        text = "Amazing product check it out https://s.click.aliexpress.com/e/_abc"
        result = parser.parse(text)
        assert result is not None
        assert result.price is None


class TestFiltering:
    def test_short_message_returns_none(self, parser: DealParser):
        text = "short"
        result = parser.parse(text)
        assert result is None

    def test_message_without_link_returns_none(self, parser: DealParser):
        text = "This is a long message about deals but has no actual link to anything"
        result = parser.parse(text)
        assert result is None


class TestShippingExtraction:
    def test_extract_free_shipping(self, parser: DealParser):
        text = "Earbuds ₪45 https://s.click.aliexpress.com/e/_abc משלוח חינם"
        result = parser.parse(text)
        assert result is not None
        assert result.shipping == "חינם"

    def test_extract_free_shipping_english(self, parser: DealParser):
        text = "Earbuds ₪45 https://s.click.aliexpress.com/e/_abc free shipping!"
        result = parser.parse(text)
        assert result is not None
        assert result.shipping == "חינם"

    def test_extract_shipping_tags(self, parser: DealParser):
        text = (
            "Camera https://s.click.aliexpress.com/e/_abc משלוח חינם "
            "עם משלוח מהיר מהמחסן הישראלי"
        )
        result = parser.parse(text)
        assert result is not None
        assert result.shipping_tags == ["משלוח חינם", "משלוח מהיר", "מחסן ישראל"]
