"""Destination routing based on category and platform."""

from __future__ import annotations

from bot.config import DestinationConfig


class DestinationRouter:
    def __init__(self, destinations: dict[str, DestinationConfig]):
        self._destinations = destinations

    def resolve(self, category: str) -> list[DestinationConfig]:
        matches: list[DestinationConfig] = []
        for destination in self._destinations.values():
            if not destination.enabled:
                continue
            if "*" in destination.categories or category in destination.categories:
                matches.append(destination)
        return matches
