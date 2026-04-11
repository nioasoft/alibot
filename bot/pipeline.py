"""Processing pipeline: orchestrates all deal processing stages."""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from bot.affiliate_pool import AffiliateLinkPool
from bot.aliexpress_client import AliExpressClient
from bot.category_resolver import CategoryResolver
from bot.dedup import DuplicateChecker
from bot.exchange_rate import get_cached_rate
from bot.image_processor import ImageProcessor, compute_image_hash
from bot.models import DailyStat, Deal, PublishQueueItem, RawMessage
from bot.parser import DealParser
from bot.resolver import LinkResolver
from bot.rewriter import ContentRewriter
from bot.router import DestinationRouter


def _canonical_product_url(product_id: str | None, fallback_url: str) -> str:
    if product_id:
        return f"https://www.aliexpress.com/item/{product_id}.html"
    return fallback_url


class Pipeline:
    def __init__(
        self,
        parser: DealParser,
        dedup: DuplicateChecker,
        resolver: LinkResolver,
        rewriter: ContentRewriter,
        image_processor: ImageProcessor,
        session: Session,
        router: DestinationRouter,
        category_resolver: CategoryResolver,
        notifier: object,
        image_dir: str = "data/images",
        aliexpress_client: Optional[AliExpressClient] = None,
        affiliate_pool: Optional[AffiliateLinkPool] = None,
    ):
        self._parser = parser
        self._dedup = dedup
        self._resolver = resolver
        self._rewriter = rewriter
        self._image_processor = image_processor
        self._session = session
        self._router = router
        self._category_resolver = category_resolver
        self._notifier = notifier
        self._image_dir = Path(image_dir)
        self._ali_client = aliexpress_client
        self._affiliate_pool = affiliate_pool

    async def process(
        self,
        text: str,
        images: list[bytes],
        source_group: str,
        telegram_message_id: int,
    ) -> Optional[Deal]:
        raw = RawMessage(
            source_group=source_group,
            telegram_message_id=telegram_message_id,
            raw_text=text,
            has_images=len(images) > 0,
            received_at=datetime.datetime.now(datetime.UTC),
            status="pending",
        )
        self._session.add(raw)
        self._session.flush()

        self._increment_stat("deals_seen")

        try:
            deal = await self._process_stages(raw, text, images, source_group)
            raw.status = "processed"
            self._session.commit()
            return deal
        except Exception as e:
            raw.status = "failed"
            raw.error_message = str(e)[:500]
            self._session.commit()
            self._increment_stat("deals_skipped_error")
            logger.error(f"Pipeline error for message {telegram_message_id}: {e}")
            if hasattr(self._notifier, "notify_error"):
                await self._notifier.notify_error(f"Pipeline error: {e}")
            return None

    async def _process_stages(
        self,
        raw: RawMessage,
        text: str,
        images: list[bytes],
        source_group: str,
    ) -> Optional[Deal]:
        parsed = self._parser.parse(text)
        if parsed is None:
            logger.debug("No AliExpress link found, skipping")
            return None

        product_id = parsed.product_id
        if product_id is None:
            product_id = await self._resolver.resolve(parsed.link)

        product_url = _canonical_product_url(product_id, parsed.link)

        ali_details = None
        if self._ali_client and self._ali_client.is_enabled and product_id:
            ali_details = self._ali_client.get_product_details(product_id)
            self._increment_stat("api_calls")
            if ali_details and ali_details.images:
                api_image = self._ali_client.download_image(ali_details.images[0])
                if api_image:
                    images = [api_image]

        text_hash = hashlib.md5((parsed.raw_text or "").lower().strip().encode()).hexdigest()

        image_hash = None
        if images:
            try:
                image_hash = compute_image_hash(images[0])
            except Exception as e:
                logger.warning(f"Image hash failed: {e}")

        if self._dedup.is_duplicate(
            product_id=product_id,
            text_hash=text_hash,
            image_hash=image_hash,
        ):
            logger.info("Duplicate deal detected, skipping")
            self._increment_stat("deals_skipped_dup")
            return None

        category_resolution = await self._category_resolver.resolve(
            product_name=ali_details.title if ali_details else parsed.raw_text[:100],
            original_text=text,
            ali_category_raw=ali_details.category if ali_details else None,
        )

        rewrite_price = None
        rewrite_currency = parsed.currency
        if ali_details and (ali_details.sale_price or ali_details.price):
            rewrite_price = ali_details.sale_price or ali_details.price
            rewrite_currency = ali_details.currency or "USD"
        elif parsed.price:
            rewrite_price = parsed.price

        rewrite_result = await self._rewriter.rewrite(
            product_name=ali_details.title if ali_details else parsed.raw_text[:100],
            price=rewrite_price,
            currency=rewrite_currency,
            shipping=parsed.shipping,
            original_text=text,
            rating=ali_details.rating if ali_details else None,
            sales_count=ali_details.orders_count if ali_details else None,
            usd_ils_rate=get_cached_rate(),
        )

        processed_images: list[bytes] = []
        for img_bytes in images:
            try:
                processed_images.append(self._image_processor.add_watermark(img_bytes))
            except Exception as e:
                logger.warning(f"Watermark failed, using original: {e}")
                processed_images.append(img_bytes)

        final_price = None
        final_currency = parsed.currency or "ILS"
        if ali_details and (ali_details.sale_price or ali_details.price):
            final_price = ali_details.sale_price or ali_details.price
            final_currency = ali_details.currency or "USD"
        elif parsed.price:
            final_price = parsed.price

        affiliate_link = None
        affiliate_account_key = None
        if self._affiliate_pool:
            affiliate_link, affiliate_account_key = self._affiliate_pool.get_affiliate_link(
                product_url,
                seed=product_id or product_url,
            )

        deal = Deal(
            raw_message_id=raw.id,
            product_id=product_id,
            product_name=rewrite_result.product_name_clean,
            original_text=text,
            rewritten_text=rewrite_result.rewritten_text,
            price=final_price or 0.0,
            original_price=parsed.original_price,
            currency=final_currency,
            shipping=parsed.shipping,
            category=category_resolution.category,
            ali_category_raw=category_resolution.ali_category_raw,
            category_source=category_resolution.source,
            affiliate_account_key=affiliate_account_key,
            affiliate_link=affiliate_link,
            product_link=product_url,
            image_hash=image_hash,
            text_hash=text_hash,
            source_group=source_group,
            created_at=datetime.datetime.now(datetime.UTC),
        )
        self._session.add(deal)
        self._session.flush()

        if processed_images:
            self._image_dir.mkdir(parents=True, exist_ok=True)
            img_path = self._image_dir / f"{deal.id}.jpg"
            img_path.write_bytes(processed_images[0])
            deal.image_path = str(img_path)

        destinations = self._router.resolve(category_resolution.category)
        for destination in destinations:
            self._session.add(
                PublishQueueItem(
                    deal_id=deal.id,
                    target_group=destination.target,
                    destination_key=destination.key,
                    platform=destination.platform,
                    target_ref=destination.target,
                    status="queued",
                    scheduled_after=datetime.datetime.now(datetime.UTC),
                )
            )

        self._session.commit()

        self._increment_stat("deals_processed")
        logger.info(
            f"Deal processed: {rewrite_result.product_name_clean} "
            f"-> {category_resolution.category} -> {len(destinations)} destinations"
        )

        return deal

    def _increment_stat(self, field: str) -> None:
        today = datetime.date.today()
        stat = self._session.query(DailyStat).filter_by(date=today).first()
        if stat is None:
            stat = DailyStat(
                date=today,
                deals_seen=0,
                deals_processed=0,
                deals_published=0,
                deals_skipped_dup=0,
                deals_skipped_error=0,
                api_calls=0,
            )
            self._session.add(stat)
            self._session.flush()
        current = getattr(stat, field) or 0
        setattr(stat, field, current + 1)
        self._session.flush()
