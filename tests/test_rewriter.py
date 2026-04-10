import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.rewriter import ContentRewriter, RewriteResult


@pytest.fixture
def rewriter():
    return ContentRewriter(api_key="sk-test", model="gpt-4o-mini")


@pytest.mark.asyncio
class TestContentRewriter:
    async def test_rewrite_returns_structured_result(self, rewriter: ContentRewriter):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {
                            "rewritten_text": "🎧 אוזניות בלוטוס מטורפות!\n💰 רק 45 ש\"ח\n🚚 משלוח חינם",
                            "category": "tech",
                            "product_name_clean": "wireless bluetooth earbuds",
                        }
                    )
                )
            )
        ]

        with patch.object(
            rewriter._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await rewriter.rewrite(
                product_name="Wireless Earbuds",
                price=45.0,
                currency="ILS",
                shipping="חינם",
                original_text="Original deal text here",
            )

        assert isinstance(result, RewriteResult)
        assert "אוזניות" in result.rewritten_text
        assert result.category == "tech"
        assert result.product_name_clean == "wireless bluetooth earbuds"

    async def test_rewrite_handles_api_error_with_fallback(self, rewriter: ContentRewriter):
        with patch.object(
            rewriter._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=Exception("API error"),
        ):
            result = await rewriter.rewrite(
                product_name="Test Product",
                price=30.0,
                currency="ILS",
                original_text="Original text for fallback",
            )

        assert result is not None
        assert result.category == "other"
        assert "Test Product" in result.rewritten_text

    async def test_rewrite_handles_invalid_json(self, rewriter: ContentRewriter):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="not valid json"))
        ]

        with patch.object(
            rewriter._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await rewriter.rewrite(
                product_name="Test",
                price=10.0,
                currency="ILS",
                original_text="Original",
            )

        assert result is not None
        assert result.category == "other"
