"""Map AliExpress categories to internal routing categories."""

from __future__ import annotations


ALLOWED_CATEGORIES = (
    "tech",
    "home",
    "fashion",
    "beauty",
    "toys",
    "sports",
    "auto",
    "other",
)

_ALIEXPRESS_CATEGORY_MAP = {
    "consumer electronics": "tech",
    "phones & telecommunications": "tech",
    "computer & office": "tech",
    "security & protection": "tech",
    "home & garden": "home",
    "home improvement": "home",
    "furniture": "home",
    "women's clothing": "fashion",
    "men's clothing": "fashion",
    "mother & kids": "toys",
    "shoes": "fashion",
    "underwear & sleepwears": "fashion",
    "luggage & bags": "fashion",
    "jewelry & accessories": "fashion",
    "beauty & health": "beauty",
    "toys & hobbies": "toys",
    "sports & entertainment": "sports",
    "automobiles & motorcycles": "auto",
    "tools": "home",
    "pet products": "home",
}


def normalize_category(value: str | None) -> str:
    if not value:
        return "other"
    normalized = value.strip().lower()
    return normalized if normalized in ALLOWED_CATEGORIES else "other"


def map_aliexpress_category(raw_category: str | None) -> str | None:
    if not raw_category:
        return None

    normalized = raw_category.strip().lower()
    return _ALIEXPRESS_CATEGORY_MAP.get(normalized)
