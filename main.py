"""Entry point: wire all components and start the bot."""

from __future__ import annotations

import asyncio
import os
import sys

import uvicorn
from dotenv import load_dotenv
from loguru import logger
from telethon import TelegramClient, Button
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from bot.config import load_config, AppConfig
from bot.models import init_db, Deal
from bot.parser import DealParser
from bot.dedup import DuplicateChecker
from bot.resolver import LinkResolver
from bot.rewriter import ContentRewriter
from bot.image_processor import ImageProcessor
from bot.aliexpress_client import AliExpressClient
from bot.pipeline import Pipeline
from bot.publisher import DealPublisher
from bot.notifier import Notifier
from bot.admin import AdminCommands
from bot.listener import TelegramListener
from dashboard.app import create_dashboard


def _setup_logging():
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(
        "data/bot.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
    )


async def _send_telegram_message(client: TelegramClient, admin_chat: str, text: str):
    await client.send_message(admin_chat, text)


async def _send_deal(
    client: TelegramClient,
    target_group: str,
    text: str,
    link: str,
    image_path: str | None = None,
    channel_link: str = "",
) -> int:
    """Send deal to target group. Returns message ID."""
    button = Button.url("🛒 לרכישה", link)
    footer = "\n\n👇 לרכישה לחצו למטה"
    if channel_link:
        footer += f"\n\n📢 הצטרפו לערוץ: {channel_link}"
    caption = f"{text}{footer}"

    if image_path:
        msg = await client.send_file(
            target_group,
            image_path,
            caption=caption,
            buttons=[button],
        )
    else:
        msg = await client.send_message(
            target_group,
            caption,
            buttons=[button],
        )
    return msg.id


async def main():
    load_dotenv()
    _setup_logging()
    logger.info("Starting AliExpress Deal Bot...")

    config = load_config("config.yaml")

    # Database
    SessionFactory = init_db("data/deals.db")
    session = SessionFactory()

    # Telethon client
    client = TelegramClient(
        "data/bot",
        config.telegram.api_id,
        config.telegram.api_hash,
    )
    await client.start(phone=config.telegram.phone)
    logger.info("Telegram client connected")

    # Notifier (needs client)
    async def send_to_admin(text: str):
        await _send_telegram_message(client, config.telegram.admin_chat, text)

    notifier = Notifier(send_message_func=send_to_admin, session=session)

    # Components
    parser = DealParser(
        min_message_length=config.parser.min_message_length,
        supported_domains=config.parser.supported_domains,
    )
    dedup = DuplicateChecker(
        session=session,
        window_hours=config.dedup.window_hours,
        image_hash_threshold=config.dedup.image_hash_threshold,
    )
    resolver = LinkResolver()
    rewriter = ContentRewriter(
        api_key=config.openai.api_key,
        model=config.openai.model,
    )
    image_processor = ImageProcessor(
        logo_path=config.watermark.logo_path,
        position=config.watermark.position,
        opacity=config.watermark.opacity,
        scale=config.watermark.scale,
    )

    # AliExpress API client
    ali_client = AliExpressClient(
        app_key=config.aliexpress.app_key,
        app_secret=config.aliexpress.app_secret,
        tracking_id=config.aliexpress.tracking_id,
    )

    # Pipeline
    pipeline = Pipeline(
        parser=parser,
        dedup=dedup,
        resolver=resolver,
        rewriter=rewriter,
        image_processor=image_processor,
        session=session,
        target_groups=config.telegram.target_groups,
        notifier=notifier,
        aliexpress_client=ali_client,
    )

    # Publisher
    async def send_deal_wrapper(target_group: str, text: str, link: str, image_path=None) -> int:
        return await _send_deal(client, target_group, text, link, image_path, config.telegram.channel_link)

    publisher = DealPublisher(
        send_func=send_deal_wrapper,
        session=session,
        min_delay=config.publishing.min_delay_seconds,
        max_delay=config.publishing.max_delay_seconds,
        max_posts_per_hour=config.publishing.max_posts_per_hour,
        quiet_hours_start=config.publishing.quiet_hours_start,
        quiet_hours_end=config.publishing.quiet_hours_end,
    )

    # Admin
    admin = AdminCommands(
        session=session,
        admin_user_id=config.telegram.admin_user_id,
        publisher=publisher,
    )

    # Listener
    listener = TelegramListener(
        client=client,
        source_groups=config.telegram.source_groups,
        min_message_length=config.parser.min_message_length,
        pipeline=pipeline,
        admin=admin,
    )
    listener.register()

    # Scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(publisher.check_queue, IntervalTrigger(minutes=3), id="publisher")
    scheduler.add_job(notifier.send_daily_summary, CronTrigger(hour=21, minute=0), id="daily_summary")
    scheduler.add_job(dedup.cleanup_old, CronTrigger(hour=3, minute=0), id="dedup_cleanup")
    scheduler.start()
    logger.info("Scheduler started")

    # Startup notification
    await notifier.notify_startup()

    # Dashboard
    dashboard_app = create_dashboard(SessionFactory, config)
    uvicorn_config = uvicorn.Config(
        dashboard_app,
        host="0.0.0.0",
        port=config.dashboard.port,
        log_level="warning",
    )
    server = uvicorn.Server(uvicorn_config)
    asyncio.create_task(server.serve())
    logger.info(f"Dashboard running on http://0.0.0.0:{config.dashboard.port}")

    # Run
    logger.info("Bot is running! Listening for deals...")
    try:
        await client.run_until_disconnected()
    finally:
        await notifier.notify_shutdown()
        scheduler.shutdown()
        session.close()


if __name__ == "__main__":
    asyncio.run(main())
