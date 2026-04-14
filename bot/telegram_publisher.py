"""Telegram publishing adapter."""

from __future__ import annotations

from telethon import TelegramClient

from bot.config import InviteLinkConfig
from bot.footer_links import FooterLinkBuilder


class TelegramPublisher:
    def __init__(
        self,
        client: TelegramClient,
        site_url: str = "",
        invite_links: list[InviteLinkConfig] | None = None,
    ) -> None:
        self._client = client
        self._footer_links = FooterLinkBuilder(
            site_url=site_url,
            invite_links=invite_links,
        )

    async def send_deal(
        self,
        target_ref: str,
        text: str,
        link: str,
        deal_id: int | None = None,
        image_path: str | None = None,
    ) -> int:
        footer = f"\n\n{self._footer_links.build_footer(link, deal_id)}"

        max_text_len = 1024 - len(footer) - 5
        if len(text) > max_text_len:
            text = text[:max_text_len] + "..."
        caption = f"{text}{footer}"

        if image_path:
            msg = await self._client.send_file(
                target_ref,
                image_path,
                caption=caption,
                link_preview=False,
            )
        else:
            msg = await self._client.send_message(
                target_ref,
                caption,
                link_preview=False,
            )
        return msg.id
