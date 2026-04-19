"""Compute source reputation from tracked click performance."""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from supabase import create_client


@dataclass(frozen=True)
class SourceReputation:
    source_group: str
    score: int
    links: int
    clicks: int
    clicked_links: int
    avg_clicks_per_link: float
    click_coverage_rate: float


class SourceIntelligence:
    def __init__(
        self,
        url: str,
        key: str,
        *,
        max_rows: int = 5000,
        min_links: int = 3,
    ) -> None:
        self._client = create_client(url, key)
        self._max_rows = max_rows
        self._min_links = min_links

    def refresh(self) -> dict[str, SourceReputation]:
        rows = self._fetch_tracking_rows()
        reputations = self._build_reputations(rows)
        logger.info(
            f"Source intelligence refresh complete: {len(reputations)} ranked sources "
            f"from {len(rows)} tracked links"
        )
        return reputations

    def _fetch_tracking_rows(self) -> list[dict]:
        rows: list[dict] = []
        page_size = 1000
        offset = 0

        while offset < self._max_rows:
            upper = min(offset + page_size - 1, self._max_rows - 1)
            result = (
                self._client.table("tracking_links")
                .select("source_group, click_count")
                .order("created_at", desc=True)
                .range(offset, upper)
                .execute()
            )
            page = result.data or []
            rows.extend(page)
            if len(page) < page_size:
                break
            offset += page_size

        return rows

    def _build_reputations(self, rows: list[dict]) -> dict[str, SourceReputation]:
        aggregates: dict[str, dict[str, float | int]] = {}

        for row in rows:
            source_group = self._normalize_source(row.get("source_group"))
            if not source_group:
                continue
            clicks = _to_int(row.get("click_count"))
            aggregate = aggregates.setdefault(
                source_group,
                {"links": 0, "clicks": 0, "clicked_links": 0},
            )
            aggregate["links"] = int(aggregate["links"]) + 1
            aggregate["clicks"] = int(aggregate["clicks"]) + clicks
            if clicks > 0:
                aggregate["clicked_links"] = int(aggregate["clicked_links"]) + 1

        reputations: dict[str, SourceReputation] = {}
        for source_group, aggregate in aggregates.items():
            links = int(aggregate["links"])
            if links < self._min_links:
                continue

            clicks = int(aggregate["clicks"])
            clicked_links = int(aggregate["clicked_links"])
            avg_clicks_per_link = clicks / links if links else 0.0
            click_coverage_rate = clicked_links / links if links else 0.0
            score = _score_source(
                avg_clicks_per_link=avg_clicks_per_link,
                click_coverage_rate=click_coverage_rate,
                links=links,
                clicks=clicks,
            )
            reputations[source_group] = SourceReputation(
                source_group=source_group,
                score=score,
                links=links,
                clicks=clicks,
                clicked_links=clicked_links,
                avg_clicks_per_link=avg_clicks_per_link,
                click_coverage_rate=click_coverage_rate,
            )

        return reputations

    @staticmethod
    def _normalize_source(value: object) -> str:
        return str(value or "").strip().lower()


def _score_source(
    *,
    avg_clicks_per_link: float,
    click_coverage_rate: float,
    links: int,
    clicks: int,
) -> int:
    raw_score = (
        avg_clicks_per_link * 24
        + click_coverage_rate * 42
        + min(links, 12)
        + min(clicks, 10) * 2
    )
    return max(0, min(100, round(raw_score)))


def _to_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(float(value))
        except ValueError:
            return 0
    return 0
