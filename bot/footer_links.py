"""Helpers for rotating invite links in social post footers."""

from __future__ import annotations

import hashlib

from bot.config import InviteLinkConfig


class FooterLinkBuilder:
    def __init__(
        self,
        site_url: str = "",
        invite_links: list[InviteLinkConfig] | None = None,
    ) -> None:
        self._site_url = site_url.strip()
        self._invite_links = [link for link in invite_links or [] if link.url.strip()]

    def select_invite_link(self, seed: int | str | None) -> InviteLinkConfig | None:
        if not self._invite_links:
            return None
        if seed is None:
            return self._invite_links[0]

        digest = hashlib.sha256(str(seed).encode("utf-8")).hexdigest()
        index = int(digest, 16) % len(self._invite_links)
        return self._invite_links[index]

    def build_footer(self, purchase_url: str, seed: int | str | None = None) -> str:
        lines = [f"🛒 לרכישה: {purchase_url}"]
        invite_link = self.select_invite_link(seed)
        if invite_link is not None:
            lines.append(f"{invite_link.footer_label}: {invite_link.url}")
        if self._site_url:
            lines.append(f"🌐 להצטרפות לכל הקבוצות: {self._site_url}")
        return "\n\n".join(lines)
