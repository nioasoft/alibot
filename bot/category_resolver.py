"""Resolve the routing category for a deal."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bot.category_mapper import map_aliexpress_category, normalize_category


@dataclass(frozen=True)
class CategoryResolution:
    category: str
    source: str
    ali_category_raw: str | None = None


_HOME_OVERRIDE_PATTERNS = (
    re.compile(
        r"\b(cat|cats|bird|birds|pigeon|pigeons|squirrel|squirrels|repellent|repeller|spike|spikes|garden|fence|yard|balcony|balconies|pet)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"חתול|חתולים|יונ(?:ה|ים)|ציפור|ציפורים|סנאי|סנאים|דוקרנ|הרחקת|מזיק|מזיקים|גינה|מרפסת|גדר",
        re.IGNORECASE,
    ),
)


def _should_override_to_home(
    *,
    mapped_category: str | None,
    product_name: str,
    original_text: str,
    ali_category_raw: str | None,
) -> bool:
    if mapped_category != "sports":
        return False

    if (ali_category_raw or "").strip().lower() != "sports & entertainment":
        return False

    haystack = f"{product_name}\n{original_text}"
    return any(pattern.search(haystack) for pattern in _HOME_OVERRIDE_PATTERNS)


class CategoryResolver:
    def __init__(self, classifier) -> None:
        self._classifier = classifier

    async def resolve(
        self,
        *,
        product_name: str,
        original_text: str,
        ali_category_raw: str | None = None,
    ) -> CategoryResolution:
        mapped = map_aliexpress_category(ali_category_raw)
        if mapped:
            if _should_override_to_home(
                mapped_category=mapped,
                product_name=product_name,
                original_text=original_text,
                ali_category_raw=ali_category_raw,
            ):
                return CategoryResolution(
                    category="home",
                    source="api_override",
                    ali_category_raw=ali_category_raw,
                )
            return CategoryResolution(
                category=mapped,
                source="api",
                ali_category_raw=ali_category_raw,
            )

        llm_category = await self._classifier.classify_category(
            product_name=product_name,
            original_text=original_text,
        )
        return CategoryResolution(
            category=normalize_category(llm_category),
            source="llm_fallback",
            ali_category_raw=ali_category_raw,
        )
