"""Telegram listener: captures new messages from source deal groups."""

from __future__ import annotations

import io
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto
from loguru import logger

from bot.pipeline import Pipeline
from bot.admin import AdminCommands


class TelegramListener:
    def __init__(
        self,
        client: TelegramClient,
        source_groups: list[str | int],
        min_message_length: int,
        pipeline: Pipeline,
        admin: AdminCommands,
    ):
        self._client = client
        self._source_groups = source_groups
        self._min_length = min_message_length
        self._pipeline = pipeline
        self._admin = admin

    def register(self) -> None:
        """Register event handlers on the Telethon client."""

        @self._client.on(events.NewMessage(chats=self._source_groups))
        async def on_source_message(event):
            await self._handle_source_message(event)

        @self._client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def on_private_message(event):
            await self._handle_admin_message(event)

        logger.info(f"Registered listeners for {len(self._source_groups)} source groups")

    async def _handle_source_message(self, event) -> None:
        message = event.message
        text = message.text or ""

        if len(text) < self._min_length:
            return

        # Download images if present
        images: list[bytes] = []
        if isinstance(message.media, MessageMediaPhoto):
            try:
                img_bytes = await self._client.download_media(message, bytes)
                if img_bytes:
                    images.append(img_bytes)
            except Exception as e:
                logger.warning(f"Failed to download image: {e}")

        source_group = ""
        if hasattr(event.chat, "username") and event.chat.username:
            source_group = f"@{event.chat.username}"
        elif hasattr(event.chat, "title"):
            source_group = event.chat.title

        logger.debug(f"New message from {source_group}: {text[:80]}...")

        await self._pipeline.process(
            text=text,
            images=images,
            source_group=source_group,
            telegram_message_id=message.id,
        )

    async def _handle_admin_message(self, event) -> None:
        sender = await event.get_sender()
        if sender is None:
            return

        response = await self._admin.handle_command(sender.id, event.text or "")
        if response:
            await event.reply(response)
