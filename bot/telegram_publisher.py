"""Telegram publishing adapter."""

from __future__ import annotations

from telethon import TelegramClient


class TelegramPublisher:
    def __init__(
        self,
        client: TelegramClient,
        channel_link: str = "",
        whatsapp_link: str = "",
    ) -> None:
        self._client = client
        self._channel_link = channel_link
        self._whatsapp_link = whatsapp_link

    async def send_deal(
        self,
        target_ref: str,
        text: str,
        link: str,
        image_path: str | None = None,
    ) -> int:
        footer = f"\n\n🛒 לרכישה: {link}"
        if self._channel_link or self._whatsapp_link:
            footer += "\n\n📢 הצטרפו אלינו:"
            if self._channel_link:
                footer += f"\nטלגרם: {self._channel_link}"
            if self._whatsapp_link:
                footer += f"\nוואטסאפ: {self._whatsapp_link}"

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
