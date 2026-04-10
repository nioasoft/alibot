"""AI-powered content rewriting and categorization using OpenAI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from openai import AsyncOpenAI
from loguru import logger

_SYSTEM_PROMPT = """אתה כותב תוכן לערוץ דילים בטלגרם. אתה מקבל מידע על דיל ומחזיר JSON.

כללים לשכתוב:
- שנה את הניסוח לגמרי (אסור להעתיק מהמקור)
- שמור על כל המידע החשוב: מוצר, מחיר, משלוח
- הוסף אימוג'ים מתאימים
- הוסף 2-3 נקודות חיוביות על המוצר
- סגנון מושך ומזמין לרכישה
- אורך: 3-5 שורות קצרות (מקסימום 400 תווים)
- כתוב בעברית בלבד
- אל תכלול לינקים בטקסט! הלינק לרכישה מופיע מתחת להודעה
- אם קיבלת מחיר בדולר ושער דולר, ציין את המחיר גם בדולר וגם בשקלים. לדוגמה: "$2.99 (כ-₪9.15)"

לקיטלוג, בחר קטגוריה אחת מ:
tech, home, fashion, beauty, toys, sports, auto, other

החזר JSON בלבד:
{"rewritten_text": "...", "category": "...", "product_name_clean": "שם מוצר נקי באנגלית"}"""


@dataclass(frozen=True)
class RewriteResult:
    rewritten_text: str
    category: str
    product_name_clean: str


class ContentRewriter:
    def __init__(self, api_key: str, model: str):
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def rewrite(
        self,
        product_name: str,
        price: Optional[float],
        currency: Optional[str],
        original_text: str,
        shipping: Optional[str] = None,
        rating: Optional[float] = None,
        sales_count: Optional[int] = None,
        usd_ils_rate: Optional[float] = None,
    ) -> RewriteResult:
        user_prompt = self._build_user_prompt(
            product_name, price, currency, shipping, rating, sales_count, original_text, usd_ils_rate
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.8,
                max_tokens=500,
            )

            raw = response.choices[0].message.content
            data = json.loads(raw)

            return RewriteResult(
                rewritten_text=data["rewritten_text"],
                category=data.get("category", "other"),
                product_name_clean=data.get("product_name_clean", product_name),
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse AI response: {e}")
            return self._fallback(product_name, price, currency, usd_ils_rate)
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return self._fallback(product_name, price, currency, usd_ils_rate)

    def _build_user_prompt(
        self,
        product_name: str,
        price: Optional[float],
        currency: Optional[str],
        shipping: Optional[str],
        rating: Optional[float],
        sales_count: Optional[int],
        original_text: str,
        usd_ils_rate: Optional[float] = None,
    ) -> str:
        parts = [f"מוצר: {product_name}"]
        if price and currency:
            symbol = "₪" if currency == "ILS" else "$"
            parts.append(f"מחיר: {symbol}{price}")
            if currency == "USD" and usd_ils_rate:
                ils_price = round(price * usd_ils_rate, 2)
                parts.append(f"מחיר בשקלים: ₪{ils_price} (שער: {usd_ils_rate})")
        if shipping:
            parts.append(f"משלוח: {shipping}")
        if rating:
            parts.append(f"דירוג: {rating}")
        if sales_count:
            parts.append(f"מכירות: {sales_count}")
        parts.append(f"\nטקסט מקורי:\n{original_text}")
        return "\n".join(parts)

    def _fallback(
        self,
        product_name: str,
        price: Optional[float],
        currency: Optional[str],
        usd_ils_rate: Optional[float] = None,
    ) -> RewriteResult:
        """Template-based fallback when AI fails."""
        price_str = ""
        if price and currency:
            if currency == "USD" and usd_ils_rate:
                ils_price = round(price * usd_ils_rate, 2)
                price_str = f"\n💰 מחיר: ${price} (כ-₪{ils_price})"
            else:
                symbol = "₪" if currency == "ILS" else "$"
                price_str = f"\n💰 מחיר: {symbol}{price}"

        text = f"🔥 {product_name}{price_str}\n👉 לפרטים נוספים לחצו על הלינק"
        return RewriteResult(
            rewritten_text=text,
            category="other",
            product_name_clean=product_name,
        )
