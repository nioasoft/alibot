"""Resolve the routing category for a deal."""

from __future__ import annotations

from dataclasses import dataclass

from bot.category_mapper import map_aliexpress_category, normalize_category


@dataclass(frozen=True)
class CategoryResolution:
    category: str
    source: str
    ali_category_raw: str | None = None


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
