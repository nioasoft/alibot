from unittest.mock import AsyncMock

import pytest

from bot.category_resolver import CategoryResolver


@pytest.mark.asyncio
async def test_category_resolver_prefers_aliexpress_mapping():
    classifier = AsyncMock()
    classifier.classify_category.return_value = "other"
    resolver = CategoryResolver(classifier)

    result = await resolver.resolve(
        product_name="Earbuds",
        original_text="great deal",
        ali_category_raw="Consumer Electronics",
    )

    assert result.category == "tech"
    assert result.source == "api"


@pytest.mark.asyncio
async def test_category_resolver_falls_back_to_llm():
    classifier = AsyncMock()
    classifier.classify_category.return_value = "sports"
    resolver = CategoryResolver(classifier)

    result = await resolver.resolve(
        product_name="Training band",
        original_text="fitness gear",
        ali_category_raw=None,
    )

    assert result.category == "sports"
    assert result.source == "llm_fallback"


@pytest.mark.asyncio
async def test_category_resolver_overrides_sports_entertainment_garden_repeller_to_home():
    classifier = AsyncMock()
    classifier.classify_category.return_value = "sports"
    resolver = CategoryResolver(classifier)

    result = await resolver.resolve(
        product_name="Spikes Repeller Cat Plastic Bird Repellent",
        original_text="דוקרנים להרחקת חתולים, יונים ומזיקים מהגינה/מרפסת",
        ali_category_raw="Sports & Entertainment",
    )

    assert result.category == "home"
    assert result.source == "api_override"


@pytest.mark.asyncio
async def test_category_resolver_keeps_real_sports_items_in_sports():
    classifier = AsyncMock()
    classifier.classify_category.return_value = "other"
    resolver = CategoryResolver(classifier)

    result = await resolver.resolve(
        product_name="Resistance Bands Set for Training",
        original_text="fitness gear for workout and exercise",
        ali_category_raw="Sports & Entertainment",
    )

    assert result.category == "sports"
    assert result.source == "api"
