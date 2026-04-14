"""Parse deal messages to extract links, prices, and product info."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedDeal:
    link: str
    product_id: Optional[str]
    price: Optional[float]
    original_price: Optional[float]
    currency: Optional[str]
    shipping: Optional[str]
    shipping_tags: list[str]
    coupon_codes: list[str]
    raw_text: str
    user_notes: Optional[str]


# Regex patterns
_ALIEXPRESS_URL = re.compile(
    r"https?://(?:www\.)?"
    r"(?:s\.click\.aliexpress\.com/e/[A-Za-z0-9_-]+"
    r"|a\.aliexpress\.com/[A-Za-z0-9_-]+"
    r"|(?:\w+\.)?aliexpress\.com/item/(\d+)\.html[^\s]*)",
    re.IGNORECASE,
)

_PRICE_ILS = re.compile(
    r"(?:₪|nis|ils)\s*(\d+(?:[.,]\d+)?)"
    r"|(\d+(?:[.,]\d+)?)\s*(?:₪|ש\"ח|שח|nis|ils)",
    re.IGNORECASE,
)

_PRICE_USD = re.compile(
    r"\$\s*(\d+(?:[.,]\d+)?)"
    r"|(\d+(?:[.,]\d+)?)\s*(?:usd|\$)",
    re.IGNORECASE,
)

_FREE_SHIPPING = re.compile(
    r"משלוח\s*חינם|free\s*shipping|חינם\s*משלוח",
    re.IGNORECASE,
)

_FAST_SHIPPING = re.compile(
    r"משלוח\s*מהיר|fast\s*shipping",
    re.IGNORECASE,
)

_ISRAEL_WAREHOUSE = re.compile(
    r"מחסן\s*ישראל(?:י)?|מהמחסן\s*הישראלי|warehouse\s*israel|from\s+israel\s+warehouse",
    re.IGNORECASE,
)

_COUPON_KEYWORD = re.compile(r"קוד(?:\s+הנחה)?|coupon|code", re.IGNORECASE)
_COUPON_TOKEN = re.compile(r"\b[A-Z0-9][A-Z0-9_-]{3,}\b")
_URL_CLEANUP = re.compile(r"https?://\S+", re.IGNORECASE)

_PRODUCT_ID_FROM_URL = re.compile(r"/item/(\d+)\.html", re.IGNORECASE)
_COUPON_STOPWORDS = {
    "HTTP",
    "HTTPS",
    "ALIEXPRESS",
    "CLICK",
    "CODE",
    "COUPON",
}


def _parse_price_value(match: re.Match) -> float:
    raw = match.group(1) or match.group(2)
    return float(raw.replace(",", "."))


def _extract_user_notes(text: str, link: str) -> Optional[str]:
    notes = text.replace(link, " ")
    notes = re.sub(r"\s+", " ", notes).strip(" \n\t-–|")
    return notes or None


def _extract_coupon_codes(text: str) -> list[str]:
    coupons: list[str] = []
    seen: set[str] = set()

    for raw_line in text.splitlines():
        line = _URL_CLEANUP.sub(" ", raw_line)
        line = line.replace("*", " ").replace("`", " ")
        if not _COUPON_KEYWORD.search(line):
            continue

        for token in _COUPON_TOKEN.findall(line.upper()):
            if token in _COUPON_STOPWORDS:
                continue
            if token not in seen:
                seen.add(token)
                coupons.append(token)

    return coupons


def _extract_shipping_tags(text: str) -> list[str]:
    tags: list[str] = []
    if _FREE_SHIPPING.search(text):
        tags.append("משלוח חינם")
    if _FAST_SHIPPING.search(text):
        tags.append("משלוח מהיר")
    if _ISRAEL_WAREHOUSE.search(text):
        tags.append("מחסן ישראל")
    return tags


class DealParser:
    def __init__(self, min_message_length: int, supported_domains: list[str]):
        self._min_length = min_message_length
        self._domains = supported_domains

    def parse(self, text: str) -> Optional[ParsedDeal]:
        if len(text) < self._min_length:
            return None

        link_match = _ALIEXPRESS_URL.search(text)
        if link_match is None:
            return None

        link = link_match.group(0)
        # Strip trailing punctuation that got captured
        link = link.rstrip(".,!?)")

        # Extract product ID from direct links
        product_id = None
        pid_match = _PRODUCT_ID_FROM_URL.search(link)
        if pid_match:
            product_id = pid_match.group(1)

        # Extract prices (all ILS matches, then USD)
        prices = self._extract_prices(text)
        price = prices.get("price")
        original_price = prices.get("original_price")
        currency = prices.get("currency")

        # Extract shipping
        shipping_tags = _extract_shipping_tags(text)
        shipping = "חינם" if "משלוח חינם" in shipping_tags else None

        return ParsedDeal(
            link=link,
            product_id=product_id,
            price=price,
            original_price=original_price,
            currency=currency,
            shipping=shipping,
            shipping_tags=shipping_tags,
            coupon_codes=_extract_coupon_codes(text),
            raw_text=text,
            user_notes=_extract_user_notes(text, link),
        )

    def _extract_prices(self, text: str) -> dict:
        # Try ILS first (more common in Hebrew deal groups)
        ils_matches = list(_PRICE_ILS.finditer(text))
        if ils_matches:
            values = sorted([_parse_price_value(m) for m in ils_matches])
            if len(values) >= 2:
                return {
                    "price": values[0],
                    "original_price": values[-1],
                    "currency": "ILS",
                }
            return {"price": values[0], "original_price": None, "currency": "ILS"}

        # Try USD
        usd_matches = list(_PRICE_USD.finditer(text))
        if usd_matches:
            values = sorted([_parse_price_value(m) for m in usd_matches])
            if len(values) >= 2:
                return {
                    "price": values[0],
                    "original_price": values[-1],
                    "currency": "USD",
                }
            return {"price": values[0], "original_price": None, "currency": "USD"}

        return {"price": None, "original_price": None, "currency": None}
