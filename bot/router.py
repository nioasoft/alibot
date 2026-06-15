"""Destination routing based on category and platform."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bot.config import DestinationConfig
from bot.models import PublishQueueItem


class DestinationRouter:
    def __init__(
        self,
        destinations: dict[str, DestinationConfig],
        session: Optional[Session] = None,
    ):
        self._destinations = destinations
        self._session = session

    def resolve(self, category: str) -> list[DestinationConfig]:
        matches: list[DestinationConfig] = []
        for destination in self._destinations.values():
            if not destination.enabled:
                continue
            if "*" in destination.categories or category in destination.categories:
                matches.append(destination)
        return matches

    def resolve_with_rotation(self, category: str) -> list[DestinationConfig]:
        """Like resolve(), but a deal is sent to only ONE Facebook group per call,
        rotating across groups (least-recently-used) instead of every group. This
        avoids the same deal being blasted to all Facebook groups at once, which
        reads as spam and risks group bans. Telegram/WhatsApp destinations are
        untouched. With no session, falls back to the full list (resolve()).
        """
        destinations = self.resolve(category)
        return self._collapse_facebook(destinations)

    def _collapse_facebook(
        self, destinations: list[DestinationConfig]
    ) -> list[DestinationConfig]:
        facebook = [d for d in destinations if d.platform == "facebook"]
        if self._session is None or len(facebook) <= 1:
            return destinations

        others = [d for d in destinations if d.platform != "facebook"]
        chosen = self._least_recently_used_facebook(facebook)
        return others + [chosen]

    def _least_recently_used_facebook(
        self, facebook: list[DestinationConfig]
    ) -> DestinationConfig:
        """Pick the Facebook group whose most recent queue item is oldest. Groups
        with no history rank as most idle, so every group gets used before any
        repeats."""
        targets = [d.target for d in facebook]
        rows = self._session.execute(
            select(
                PublishQueueItem.target_ref,
                func.max(PublishQueueItem.id),
            )
            .where(
                PublishQueueItem.platform == "facebook",
                PublishQueueItem.target_ref.in_(targets),
            )
            .group_by(PublishQueueItem.target_ref)
        ).all()
        last_id_by_target = {target_ref: max_id for target_ref, max_id in rows}

        # Sort key: (has_history, last_item_id). Never-used groups (has_history
        # False) come first; among used groups, the smallest last id is oldest.
        def sort_key(destination: DestinationConfig) -> tuple[bool, int]:
            last_id = last_id_by_target.get(destination.target)
            return (last_id is not None, last_id or 0)

        return min(facebook, key=sort_key)
