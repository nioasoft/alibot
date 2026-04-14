"""AI-powered content rewriting and categorization using OpenAI."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from openai import AsyncOpenAI
from loguru import logger

from bot.aliexpress_client import PromoCode

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
- אל תכתוב מספרי מחיר, סימני מטבע, או המרות לשקלים. שורת המחיר תתווסף אוטומטית מחוץ לטקסט.

לקיטלוג, בחר קטגוריה אחת מ:
tech, home, fashion, beauty, toys, sports, auto, other

החזר JSON בלבד:
{"rewritten_text": "...", "category": "...", "product_name_clean": "שם מוצר נקי באנגלית"}"""

_CLASSIFIER_PROMPT = """אתה מסווג דילי AliExpress לקטגוריה אחת בלבד.

בחר רק אחת מהאפשרויות:
tech, home, fashion, beauty, toys, sports, auto, other

החזר JSON בלבד:
{"category": "..."}"""

_PRICE_LINE_PATTERN = re.compile(
    r"(?i)(?:₪\s*\d[\d.,]*|\$\s*\d[\d.,]*|\d[\d.,]*\s*(?:ש\"ח|שח|₪|\$)|כ-\s*₪\s*\d[\d.,]*|כ-\s*\$\s*\d[\d.,]*)"
)


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
        user_notes: Optional[str] = None,
        shipping: Optional[str] = None,
        rating: Optional[float] = None,
        sales_count: Optional[int] = None,
        usd_ils_rate: Optional[float] = None,
    ) -> RewriteResult:
        user_prompt = self._build_user_prompt(
            product_name,
            price,
            currency,
            shipping,
            rating,
            sales_count,
            original_text,
            usd_ils_rate,
            user_notes,
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
                rewritten_text=self.finalize_text(
                    data["rewritten_text"],
                    price=price,
                    currency=currency,
                    usd_ils_rate=usd_ils_rate,
                ),
                category=data.get("category", "other"),
                product_name_clean=data.get("product_name_clean", product_name),
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse AI response: {e}")
            return self._fallback(product_name, price, currency, usd_ils_rate)
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return self._fallback(product_name, price, currency, usd_ils_rate)

    async def classify_category(
        self,
        product_name: str,
        original_text: str,
    ) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _CLASSIFIER_PROMPT},
                    {
                        "role": "user",
                        "content": f"מוצר: {product_name}\n\nטקסט מקורי:\n{original_text}",
                    },
                ],
                temperature=0.1,
                max_tokens=50,
            )
            raw = response.choices[0].message.content
            data = json.loads(raw)
            category = str(data.get("category", "other")).strip().lower()
            return category or "other"
        except Exception as e:
            logger.warning(f"Category classification failed: {e}")
            return "other"

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
        user_notes: Optional[str] = None,
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
        if user_notes:
            parts.append(f"\nדגשים או הוראות מהמשתמש:\n{user_notes}")
        parts.append(f"\nטקסט מקורי:\n{original_text}")
        return "\n".join(parts)

    def finalize_text(
        self,
        rewritten_text: str,
        price: Optional[float],
        currency: Optional[str],
        usd_ils_rate: Optional[float] = None,
        shipping_tags: Optional[list[str]] = None,
        coupon_codes: Optional[list[str]] = None,
        promo_codes: Optional[list[PromoCode]] = None,
    ) -> str:
        body = self._strip_price_lines(rewritten_text)
        extra_lines = self._build_extra_lines(
            price=price,
            currency=currency,
            usd_ils_rate=usd_ils_rate,
            shipping_tags=shipping_tags or [],
            coupon_codes=coupon_codes or [],
            promo_codes=promo_codes or [],
        )
        if body and extra_lines:
            return f"{body}\n" + "\n".join(extra_lines)
        if extra_lines:
            return "\n".join(extra_lines)
        return body

    @staticmethod
    def _strip_price_lines(text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        filtered = [line for line in lines if not _PRICE_LINE_PATTERN.search(line)]
        return "\n".join(filtered).strip()

    @staticmethod
    def _format_amount(value: float) -> str:
        formatted = f"{value:.2f}"
        if "." in formatted:
            formatted = formatted.rstrip("0").rstrip(".")
        return formatted

    def _format_price_line(
        self,
        price: Optional[float],
        currency: Optional[str],
        usd_ils_rate: Optional[float] = None,
    ) -> str:
        if not price or not currency:
            return ""

        if currency == "USD":
            usd_amount = self._format_amount(price)
            if usd_ils_rate:
                ils_amount = self._format_amount(round(price * usd_ils_rate, 2))
                return f"💰 מחיר: ${usd_amount} (כ-₪{ils_amount})"
            return f"💰 מחיר: ${usd_amount}"

        if currency == "ILS":
            return f"💰 מחיר: ₪{self._format_amount(price)}"

        return f"💰 מחיר: {currency} {self._format_amount(price)}"

    def _build_extra_lines(
        self,
        price: Optional[float],
        currency: Optional[str],
        usd_ils_rate: Optional[float],
        shipping_tags: list[str],
        coupon_codes: list[str],
        promo_codes: list[PromoCode],
    ) -> list[str]:
        lines: list[str] = []

        price_line = self._format_price_line(price, currency, usd_ils_rate)
        if price_line:
            lines.append(price_line)

        shipping_line = self._format_shipping_line(shipping_tags)
        if shipping_line:
            lines.append(shipping_line)

        lines.extend(self._format_coupon_lines(coupon_codes, promo_codes))
        return lines

    @staticmethod
    def _format_shipping_line(shipping_tags: list[str]) -> str:
        if not shipping_tags:
            return ""
        unique_tags = list(dict.fromkeys(tag.strip() for tag in shipping_tags if tag.strip()))
        return f"🚚 {' · '.join(unique_tags)}"

    @staticmethod
    def _format_coupon_lines(
        coupon_codes: list[str],
        promo_codes: list[PromoCode],
    ) -> list[str]:
        lines: list[str] = []
        seen: set[str] = set()

        for promo in promo_codes:
            code = promo.code.strip().upper()
            if not code or code in seen:
                continue
            seen.add(code)
            details: list[str] = []
            if promo.value:
                details.append(promo.value)
            if promo.minimum_spend and promo.minimum_spend not in " ".join(details):
                details.append(f"מינימום {promo.minimum_spend}")
            suffix = f" - {' | '.join(details)}" if details else ""
            lines.append(f"🎟️ קוד הנחה: {code}{suffix}")

        source_only_codes = []
        for code in coupon_codes:
            normalized = code.strip().upper()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            source_only_codes.append(normalized)

        if source_only_codes:
            lines.append(f"🎟️ קוד הנחה: {', '.join(source_only_codes)}")

        return lines

    def _fallback(
        self,
        product_name: str,
        price: Optional[float],
        currency: Optional[str],
        usd_ils_rate: Optional[float] = None,
    ) -> RewriteResult:
        """Template-based fallback when AI fails."""
        body = f"🔥 {product_name}\n👉 לפרטים נוספים לחצו על הלינק"
        return RewriteResult(
            rewritten_text=self.finalize_text(body, price, currency, usd_ils_rate),
            category="other",
            product_name_clean=product_name,
        )
