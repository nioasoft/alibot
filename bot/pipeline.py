"""Processing pipeline: orchestrates all deal processing stages."""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session
from loguru import logger

from bot.parser import DealParser, ParsedDeal
from bot.dedup import DuplicateChecker
from bot.resolver import LinkResolver
from bot.exchange_rate import get_cached_rate
from bot.rewriter import ContentRewriter
from bot.image_processor import ImageProcessor, compute_image_hash
from bot.models import RawMessage, Deal, PublishQueueItem, DailyStat
from bot.aliexpress_client import AliExpressClient


class Pipeline:
    def __init__(
        self,
        parser: DealParser,
        dedup: DuplicateChecker,
        resolver: LinkResolver,
        rewriter: ContentRewriter,
        image_processor: ImageProcessor,
        session: Session,
        target_groups: dict[str, str],
        notifier: object,
        image_dir: str = "data/images",
        aliexpress_client: Optional[AliExpressClient] = None,
    ):
        self._parser = parser
        self._dedup = dedup
        self._resolver = resolver
        self._rewriter = rewriter
        self._image_processor = image_processor
        self._session = session
        self._target_groups = target_groups
        self._notifier = notifier
        self._image_dir = Path(image_dir)
        self._ali_client = aliexpress_client

    async def process(
        self,
        text: str,
        images: list[bytes],
        source_group: str,
        telegram_message_id: int,
    ) -> Optional[Deal]:
        # Step 0: Save raw message
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
        # Step 1: Parse
        parsed = self._parser.parse(text)
        if parsed is None:
            logger.debug("No AliExpress link found, skipping")
            return None

        # Step 2: Resolve link -> product ID
        product_id = parsed.product_id
        if product_id is None:
            product_id = await self._resolver.resolve(parsed.link)

        # Step 2.5: Enrich from AliExpress API
        ali_details = None
        affiliate_link = None
        if self._ali_client and self._ali_client.is_enabled and product_id:
            ali_details = self._ali_client.get_product_details(product_id)
            affiliate_link = self._ali_client.get_affiliate_link(parsed.link)
            self._increment_stat("api_calls")

            # Use HD images from API if available
            if ali_details and ali_details.images:
                api_image = self._ali_client.download_image(ali_details.images[0])
                if api_image:
                    images = [api_image]  # Replace source images with HD API image

        # Step 3: Compute hashes
        text_hash = hashlib.md5(
            (parsed.raw_text or "").lower().strip().encode()
        ).hexdigest()

        image_hash = None
        if images:
            try:
                image_hash = compute_image_hash(images[0])
            except Exception as e:
                logger.warning(f"Image hash failed: {e}")

        # Step 4: Dedup check
        if self._dedup.is_duplicate(
            product_id=product_id,
            text_hash=text_hash,
            image_hash=image_hash,
        ):
            logger.info("Duplicate deal detected, skipping")
            self._increment_stat("deals_skipped_dup")
            return None

        # Step 5: AI rewrite + categorize
        # Determine price for rewriter (same logic as DB)
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

        # Step 6: Process images (watermark)
        processed_images: list[bytes] = []
        for img_bytes in images:
            try:
                processed = self._image_processor.add_watermark(img_bytes)
                processed_images.append(processed)
            except Exception as e:
                logger.warning(f"Watermark failed, using original: {e}")
                processed_images.append(img_bytes)

        # Step 7: Determine best price (API > parsed > None)
        final_price = None
        final_currency = parsed.currency or "ILS"
        if ali_details and (ali_details.sale_price or ali_details.price):
            final_price = ali_details.sale_price or ali_details.price
            final_currency = ali_details.currency or "USD"
        elif parsed.price:
            final_price = parsed.price

        # Save deal to DB
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
            category=rewrite_result.category,
            product_link=affiliate_link or parsed.link,
            image_hash=image_hash,
            text_hash=text_hash,
            source_group=source_group,
            created_at=datetime.datetime.now(datetime.UTC),
        )
        self._session.add(deal)
        self._session.flush()

        # Save processed image to disk for publisher
        if processed_images:
            self._image_dir.mkdir(parents=True, exist_ok=True)
            img_path = self._image_dir / f"{deal.id}.jpg"
            img_path.write_bytes(processed_images[0])
            deal.image_path = str(img_path)

        # Step 8: Enqueue for publishing
        target = self._target_groups.get(rewrite_result.category)
        if target is None:
            target = self._target_groups.get("default", "")

        queue_item = PublishQueueItem(
            deal_id=deal.id,
            target_group=target,
            status="queued",
            scheduled_after=datetime.datetime.now(datetime.UTC),
        )
        self._session.add(queue_item)
        self._session.commit()

        self._increment_stat("deals_processed")
        logger.info(
            f"Deal processed: {rewrite_result.product_name_clean} "
            f"-> {rewrite_result.category} -> queued"
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
