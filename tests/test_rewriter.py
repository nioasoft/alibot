import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.aliexpress_client import PromoCode
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

    async def test_classify_category_returns_structured_value(self, rewriter: ContentRewriter):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content=json.dumps({"category": "sports"})))
        ]

        with patch.object(
            rewriter._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await rewriter.classify_category(
                product_name="Training band",
                original_text="Resistance band for workouts",
            )

        assert result == "sports"

    async def test_finalize_text_adds_coupon_and_shipping_lines(self, rewriter: ContentRewriter):
        text = rewriter.finalize_text(
            "🔥 מצלמה לבית",
            price=38.6,
            currency="USD",
            usd_ils_rate=3.7,
            shipping_tags=["משלוח חינם", "משלוח מהיר"],
            coupon_codes=["ILAPR2", "DSB2"],
            promo_codes=[
                PromoCode(
                    code="SAVE7",
                    value="On order over USD 10, get USD 7 off",
                )
            ],
        )

        assert "💰 מחיר: $38.6" in text
        assert "🚚 משלוח חינם · משלוח מהיר" in text
        assert "🎟️ קוד הנחה: SAVE7 - On order over USD 10, get USD 7 off" in text
        assert "🎟️ קוד הנחה: ILAPR2, DSB2" in text

    async def test_build_user_prompt_marks_original_text_as_untrusted(self, rewriter: ContentRewriter):
        prompt = rewriter._build_user_prompt(
            product_name="Xiaomi 67W USB Super Fast Charger",
            price=1.5,
            currency="USD",
            shipping=None,
            rating=4.8,
            sales_count=120,
            original_text="מטען נייד 20,000mAh עם מסך מראה",
        )

        assert "מקור האמת" in prompt
        assert "טקסט מקורי לא מהימן" in prompt
        assert "Xiaomi 67W USB Super Fast Charger" in prompt
