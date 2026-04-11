"""Weighted affiliate link generation across multiple AliExpress accounts."""

from __future__ import annotations

import hashlib
from typing import Optional


class AffiliateLinkPool:
    def __init__(self, clients: dict[str, object], distribution: dict[str, int]):
        self._clients = clients
        self._distribution = distribution

    def _weighted_accounts(self) -> list[tuple[str, int, object]]:
        weighted: list[tuple[str, int, object]] = []
        for key, weight in self._distribution.items():
            client = self._clients.get(key)
            if client is None or weight <= 0:
                continue
            if not getattr(client, "is_enabled", False):
                continue
            weighted.append((key, weight, client))
        return weighted

    def pick_account_key(self, seed: str) -> Optional[str]:
        weighted = self._weighted_accounts()
        if not weighted:
            return None

        total = sum(weight for _, weight, _ in weighted)
        bucket = int(hashlib.md5(seed.encode()).hexdigest(), 16) % total
        running = 0
        for key, weight, _ in weighted:
            running += weight
            if bucket < running:
                return key
        return weighted[-1][0]

    def get_affiliate_link(self, product_url: str, seed: str) -> tuple[Optional[str], Optional[str]]:
        weighted = self._weighted_accounts()
        if not weighted:
            return None, None

        preferred_key = self.pick_account_key(seed)
        ordered_keys = [preferred_key] if preferred_key else []
        ordered_keys.extend(key for key, _, _ in weighted if key != preferred_key)

        for key in ordered_keys:
            client = self._clients[key]
            link = client.get_affiliate_link(product_url)
            if link:
                return link, key

        return None, preferred_key
