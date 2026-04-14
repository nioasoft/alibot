"""Quality scoring and priority decisions for incoming deals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bot.aliexpress_client import select_best_sale_price


@dataclass(frozen=True)
class QualityDecision:
    accepted: bool
    score: int
    priority: int
    reason: str
    is_manual: bool = False


class QualityGate:
    def __init__(
        self,
        manual_source_groups: list[str] | None = None,
        min_score_external: int = 45,
        min_score_hot_products: int = 60,
        manual_priority: int = 1000,
        idle_destination_hours: int = 6,
        idle_min_score: int = 20,
        idle_priority_boost: int = 150,
    ) -> None:
        self._manual_sources = {
            self._normalize_source(group)
            for group in (manual_source_groups or [])
            if self._normalize_source(group)
        }
        self._min_score_external = min_score_external
        self._min_score_hot_products = min_score_hot_products
        self._manual_priority = manual_priority
        self.idle_destination_hours = idle_destination_hours
        self.idle_min_score = idle_min_score
        self.idle_priority_boost = idle_priority_boost

    def evaluate_pipeline(
        self,
        source_group: str,
        ali_details: Any | None,
        category_source: str | None,
        affiliate_link_ready: bool,
        has_image: bool,
        idle_override: bool = False,
    ) -> QualityDecision:
        if self.is_manual_source(source_group):
            return QualityDecision(
                accepted=True,
                score=100,
                priority=self._manual_priority,
                reason="manual_source",
                is_manual=True,
            )

        score = self._score_from_metrics(
            orders=getattr(ali_details, "orders_count", None),
            rating=getattr(ali_details, "rating", None),
            original_price=getattr(ali_details, "price", None),
            sale_price=select_best_sale_price(
                getattr(ali_details, "sale_price", None),
                getattr(ali_details, "app_sale_price", None),
            ),
            has_image=has_image or bool(getattr(ali_details, "images", [])),
            category_source=category_source,
            affiliate_link_ready=affiliate_link_ready,
            missing_details=ali_details is None,
        )
        accepted = score >= self._min_score_external
        reason = "quality_pass" if accepted else "quality_below_threshold"
        priority = score

        if not accepted and idle_override and score >= self.idle_min_score:
            accepted = True
            reason = "idle_destination_override"
            priority += self.idle_priority_boost

        return QualityDecision(accepted=accepted, score=score, priority=priority, reason=reason)

    def evaluate_hot_product(
        self,
        *,
        orders: int | None,
        original_price: float | None,
        sale_price: float | None,
        has_image: bool,
        category_source: str | None,
        affiliate_link_ready: bool,
        idle_override: bool = False,
    ) -> QualityDecision:
        score = self._score_from_metrics(
            orders=orders,
            rating=None,
            original_price=original_price,
            sale_price=sale_price,
            has_image=has_image,
            category_source=category_source,
            affiliate_link_ready=affiliate_link_ready,
            missing_details=False,
        )
        accepted = score >= self._min_score_hot_products
        reason = "quality_pass" if accepted else "quality_below_threshold"
        priority = score

        if not accepted and idle_override and score >= self.idle_min_score:
            accepted = True
            reason = "idle_destination_override"
            priority += self.idle_priority_boost

        return QualityDecision(accepted=accepted, score=score, priority=priority, reason=reason)

    def is_manual_source(self, source_group: str | None) -> bool:
        return self._normalize_source(source_group) in self._manual_sources

    @staticmethod
    def _normalize_source(source_group: str | None) -> str:
        return (source_group or "").strip().lower()

    def _score_from_metrics(
        self,
        *,
        orders: int | None,
        rating: float | None,
        original_price: float | None,
        sale_price: float | None,
        has_image: bool,
        category_source: str | None,
        affiliate_link_ready: bool,
        missing_details: bool,
    ) -> int:
        score = 0
        score += self._score_orders(orders)
        score += self._score_rating(rating)
        score += self._score_discount(original_price, sale_price)

        if has_image:
            score += 10
        if category_source == "api":
            score += 5
        elif category_source == "llm_fallback":
            score -= 5
        if affiliate_link_ready:
            score += 5
        else:
            score -= 10
        if missing_details:
            score -= 25

        return max(0, min(100, score))

    @staticmethod
    def _score_orders(orders: int | None) -> int:
        if not orders:
            return 0
        if orders >= 500:
            return 35
        if orders >= 200:
            return 30
        if orders >= 100:
            return 24
        if orders >= 50:
            return 18
        if orders >= 20:
            return 10
        if orders >= 5:
            return 5
        return 0

    @staticmethod
    def _score_rating(rating: float | None) -> int:
        if not rating:
            return 0
        if rating >= 4.8:
            return 25
        if rating >= 4.6:
            return 22
        if rating >= 4.4:
            return 18
        if rating >= 4.2:
            return 12
        if rating >= 4.0:
            return 6
        return 0

    @staticmethod
    def _score_discount(original_price: float | None, sale_price: float | None) -> int:
        if not original_price or not sale_price or original_price <= 0 or sale_price >= original_price:
            return 0
        discount_pct = ((original_price - sale_price) / original_price) * 100
        if discount_pct >= 50:
            return 20
        if discount_pct >= 35:
            return 15
        if discount_pct >= 20:
            return 10
        if discount_pct >= 10:
            return 5
        return 0
