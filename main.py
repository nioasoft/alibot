"""Entry point: wire all components and start the bot."""

from __future__ import annotations

import asyncio
import sys

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from loguru import logger
from telethon import TelegramClient

from bot.admin import AdminCommands
from bot.affiliate_pool import AffiliateLinkPool
from bot.affiliate_order_sync import AffiliateOrderSync
from bot.aliexpress_client import AliExpressClient
from bot.aliexpress_pool import AliExpressClientPool
from bot.category_resolver import CategoryResolver
from bot.config import AppConfig, load_config
from bot.dedup import DuplicateChecker
from bot.exchange_rate import fetch_usd_ils_rate
from bot.facebook_publisher import FacebookPublisher
from bot.fork_debug import install_fork_debugging
from bot.hot_products import HotProductFetcher
from bot.http_client import close_sync_client
from bot.image_processor import ImageProcessor
from bot.listener import TelegramListener
from bot.models import init_db
from bot.notifier import Notifier
from bot.openai_runtime import install_openai_platform_override
from bot.parser import DealParser
from bot.pipeline import Pipeline
from bot.publisher import DealPublisher
from bot.quality import QualityGate
from bot.resolver import LinkResolver
from bot.rewriter import ContentRewriter
from bot.router import DestinationRouter
from bot.source_intelligence import SourceIntelligence
from bot.telegram_publisher import TelegramPublisher
from bot.supabase_publisher import SupabasePublisher
from bot.web_publisher import WebPublisher
from bot.whatsapp_publisher import WhatsAppPublisher
from dashboard.app import create_dashboard


def _setup_logging() -> None:
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


def _build_aliexpress_clients(
    config: AppConfig,
) -> tuple[AliExpressClientPool, AffiliateLinkPool, dict[str, AliExpressClient]]:
    catalog_clients: dict[str, AliExpressClient] = {}
    affiliate_clients: dict[str, AliExpressClient] = {}
    for key, account in config.aliexpress.accounts.items():
        catalog_clients[key] = AliExpressClient(
            app_key=account.app_key,
            app_secret=account.app_secret,
            tracking_id="",
            account_key=key,
            require_tracking_id=False,
        )
        affiliate_clients[key] = AliExpressClient(
            app_key=account.app_key,
            app_secret=account.app_secret,
            tracking_id=account.tracking_id,
            account_key=key,
        )

    catalog_client = AliExpressClientPool(
        clients=catalog_clients,
        preferred_key=config.aliexpress.catalog_account,
    )

    affiliate_pool = AffiliateLinkPool(
        clients=affiliate_clients,
        distribution=config.aliexpress.affiliate_distribution,
    )
    return catalog_client, affiliate_pool, affiliate_clients


async def main():
    load_dotenv()
    _setup_logging()
    install_fork_debugging()
    install_openai_platform_override()
    logger.info("Starting AliExpress Deal Bot...")

    config = load_config("config.yaml")

    session_factory = init_db("data/deals.db")
    session = session_factory()

    client = TelegramClient(
        "data/bot",
        config.telegram.api_id,
        config.telegram.api_hash,
    )
    await client.start(phone=config.telegram.phone)
    logger.info("Telegram client connected")

    async def send_to_admin(text: str):
        await _send_telegram_message(client, config.telegram.admin_chat, text)

    notifier = Notifier(send_message_func=send_to_admin, session=session)

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
    router = DestinationRouter(config.publishing.destinations or {}, session=session)
    category_resolver = CategoryResolver(rewriter)
    quality_gate = QualityGate(
        manual_source_groups=config.telegram.manual_source_groups,
        min_score_external=config.quality.min_score_external,
        min_score_hot_products=config.quality.min_score_hot_products,
        manual_priority=config.quality.manual_priority,
        idle_destination_hours=config.quality.idle_destination_hours,
        idle_min_score=config.quality.idle_min_score,
        idle_priority_boost=config.quality.idle_priority_boost,
        source_reputation_enabled=config.quality.source_reputation_enabled,
        source_reputation_boost_max=config.quality.source_reputation_boost_max,
        source_reputation_penalty_max=config.quality.source_reputation_penalty_max,
        require_affiliate_link=config.quality.require_affiliate_link,
        min_orders=config.quality.min_orders,
        min_rating=config.quality.min_rating,
        demand_override_min_orders=config.quality.demand_override_min_orders,
        demand_override_min_score=config.quality.demand_override_min_score,
        demand_boost_max=config.quality.demand_boost_max,
        demand_penalty_max=config.quality.demand_penalty_max,
        demand_positive_terms=config.quality.demand_positive_terms,
        demand_negative_terms=config.quality.demand_negative_terms,
        disabled_sources=config.quality.disabled_sources,
        disabled_source_categories=config.quality.disabled_source_categories,
        source_score_adjustments=config.quality.source_score_adjustments,
        source_category_score_adjustments=config.quality.source_category_score_adjustments,
    )
    source_intelligence = None
    if config.supabase and config.quality.source_reputation_enabled:
        source_intelligence = SourceIntelligence(
            url=config.supabase.url,
            key=config.supabase.service_key,
            max_rows=config.quality.source_reputation_max_rows,
            min_links=config.quality.source_reputation_min_links,
            lookback_days=config.quality.source_reputation_lookback_days,
        )
        quality_gate.set_source_reputations(source_intelligence.refresh())

    catalog_client, affiliate_pool, affiliate_clients = _build_aliexpress_clients(config)

    pipeline = Pipeline(
        parser=parser,
        dedup=dedup,
        resolver=resolver,
        rewriter=rewriter,
        image_processor=image_processor,
        session=session,
        router=router,
        category_resolver=category_resolver,
        notifier=notifier,
        aliexpress_client=catalog_client,
        affiliate_pool=affiliate_pool,
        quality_gate=quality_gate,
        min_queue_delay_seconds=config.publishing.min_delay_seconds,
        max_queue_delay_seconds=config.publishing.max_delay_seconds,
    )

    telegram_publisher = TelegramPublisher(
        client=client,
        site_url=config.marketing.site_url,
        invite_links=config.marketing.invite_links,
    )
    whatsapp_publisher = WhatsAppPublisher(
        base_url=config.whatsapp.service_url,
    )
    facebook_publisher = FacebookPublisher(
        service_url=config.facebook.service_url,
        site_url=config.marketing.site_url,
        comment_on_post=config.facebook.comment_links_as_comment,
        session=session,
        notify_func=send_to_admin,
    )
    if config.supabase:
        web_publisher = SupabasePublisher(
            url=config.supabase.url,
            key=config.supabase.service_key,
        )
    else:
        web_publisher = WebPublisher(enabled=False)

    publisher = DealPublisher(
        session=session,
        min_delay=config.publishing.min_delay_seconds,
        max_delay=config.publishing.max_delay_seconds,
        max_posts_per_hour=config.publishing.max_posts_per_hour,
        quiet_hours_start=config.publishing.quiet_hours_start,
        quiet_hours_end=config.publishing.quiet_hours_end,
        telegram_publisher=telegram_publisher,
        whatsapp_publisher=whatsapp_publisher,
        facebook_publisher=facebook_publisher,
        web_publisher=web_publisher,
        site_url=config.marketing.site_url,
        tracking_base_url=config.tracking.base_url,
        tracking_api_secret=config.tracking.api_secret,
        tracked_link_percentage_by_platform=config.tracking.tracked_link_percentage_by_platform,
        invite_links=config.marketing.invite_links,
        destinations=config.publishing.destinations,
        weekend_reduced_rate_factor=config.publishing.weekend_reduced_rate_factor,
        weekend_reduced_start_weekday=config.publishing.weekend_reduced_start_weekday,
        weekend_reduced_start_hour=config.publishing.weekend_reduced_start_hour,
        weekend_reduced_end_weekday=config.publishing.weekend_reduced_end_weekday,
        weekend_reduced_end_hour=config.publishing.weekend_reduced_end_hour,
        queue_item_max_age_hours=config.publishing.queue_item_max_age_hours,
    )

    order_sync = None
    if config.supabase and config.affiliate_orders.enabled:
        order_sync = AffiliateOrderSync(
            clients=affiliate_clients,
            url=config.supabase.url,
            key=config.supabase.service_key,
            product_details_client=catalog_client,
            lookback_days=config.affiliate_orders.lookback_days,
            page_size=config.affiliate_orders.page_size,
            locale_site=config.affiliate_orders.locale_site,
        )

    admin = AdminCommands(
        session=session,
        admin_user_id=config.telegram.admin_user_id,
        publisher=publisher,
    )

    listener = TelegramListener(
        client=client,
        source_groups=config.telegram.source_groups,
        min_message_length=config.parser.min_message_length,
        pipeline=pipeline,
        admin=admin,
    )
    listener.register()

    hot_fetcher = HotProductFetcher(
        ali_api=catalog_client,
        rewriter=rewriter,
        image_processor=image_processor,
        session=session,
        router=router,
        category_resolver=category_resolver,
        affiliate_pool=affiliate_pool,
        max_products_per_run=config.publishing.hot_products_per_run,
        quality_gate=quality_gate,
        min_queue_delay_seconds=config.publishing.min_delay_seconds,
        max_queue_delay_seconds=config.publishing.max_delay_seconds,
    )

    scheduler = AsyncIOScheduler()
    await fetch_usd_ils_rate()
    scheduler.add_job(publisher.check_queue, IntervalTrigger(minutes=3), id="publisher")
    scheduler.add_job(notifier.send_daily_summary, CronTrigger(hour=21, minute=0), id="daily_summary")
    scheduler.add_job(dedup.cleanup_old, CronTrigger(hour=3, minute=0), id="dedup_cleanup")
    scheduler.add_job(fetch_usd_ils_rate, CronTrigger(hour=8, minute=0), id="exchange_rate")
    scheduler.add_job(
        hot_fetcher.fetch_and_queue,
        IntervalTrigger(hours=config.publishing.hot_products_interval_hours),
        id="hot_products",
    )
    if source_intelligence is not None:
        scheduler.add_job(
            lambda: quality_gate.set_source_reputations(source_intelligence.refresh()),
            IntervalTrigger(minutes=config.quality.source_reputation_refresh_minutes),
            id="source_intelligence_refresh",
        )
    if hasattr(web_publisher, "cleanup_old_images"):
        scheduler.add_job(
            web_publisher.cleanup_old_images,
            CronTrigger(hour=4, minute=30),
            id="supabase_cleanup",
        )
    if order_sync and order_sync.is_enabled:
        scheduler.add_job(
            order_sync.sync_recent_orders,
            IntervalTrigger(minutes=config.affiliate_orders.interval_minutes),
            id="affiliate_orders_sync",
        )
    scheduler.start()
    logger.info("Scheduler started")

    if order_sync and order_sync.is_enabled:
        await order_sync.sync_recent_orders()

    await notifier.notify_startup()

    dashboard_app = create_dashboard(session_factory, config)
    uvicorn_config = uvicorn.Config(
        dashboard_app,
        host="0.0.0.0",
        port=config.dashboard.port,
        log_level="warning",
    )
    server = uvicorn.Server(uvicorn_config)
    asyncio.create_task(server.serve())
    logger.info(f"Dashboard running on http://0.0.0.0:{config.dashboard.port}")

    logger.info("Bot is running! Listening for deals...")
    try:
        await client.run_until_disconnected()
    finally:
        await notifier.notify_shutdown()
        scheduler.shutdown()
        # Close pooled HTTP clients so keep-alive connections are torn down cleanly.
        for closeable in (resolver, whatsapp_publisher, facebook_publisher):
            try:
                await closeable.aclose()
            except Exception:  # best-effort shutdown; never mask the real exit reason
                pass
        close_sync_client()
        session.close()


if __name__ == "__main__":
    asyncio.run(main())
