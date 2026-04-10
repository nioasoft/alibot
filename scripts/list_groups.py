"""List all groups/channels the Telegram account is a member of."""

import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat
from bot.config import load_config

load_dotenv()
config = load_config("config.yaml")

client = TelegramClient(
    "data/bot",
    config.telegram.api_id,
    config.telegram.api_hash,
)


async def main():
    await client.start(phone=config.telegram.phone)
    print("\n✅ Connected!\n")
    print("=" * 60)
    print("קבוצות וערוצים:")
    print("=" * 60)

    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if isinstance(entity, (Channel, Chat)):
            username = f"@{entity.username}" if hasattr(entity, "username") and entity.username else ""
            kind = "ערוץ" if getattr(entity, "broadcast", False) else "קבוצה"
            members = getattr(entity, "participants_count", "?")
            print(f"  {kind:6} | {username:25} | {dialog.name[:40]:40} | {members} members")

    print("\n" + "=" * 60)
    print("Done!")


asyncio.run(main())
