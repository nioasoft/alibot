"""Auto-fetch and publish trending AliExpress products."""

from __future__ import annotations

import datetime
import hashlib
import tempfile
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger
from sqlalchemy.orm import Session

from bot.affiliate_pool import AffiliateLinkPool
from bot.category_resolver import CategoryResolver
from bot.exchange_rate import get_cached_rate
from bot.image_processor import compute_image_hash
from bot.models import Deal, PublishQueueItem, RawMessage
from bot.rewriter import ContentRewriter
from bot.router import DestinationRouter

# Popular search terms for Israeli audience
SEARCH_QUERIES = [
    "bluetooth earbuds",
    "phone case",
    "led strip lights",
    "smart watch",
    "usb c cable",
    "kitchen gadgets",
    "car accessories",
    "home organization",
    "portable speaker",
    "wireless charger",
    "laptop stand",
    "pet accessories",
    "garden tools",
    "kids toys",
    "makeup brushes",
    "sport accessories",
    "cleaning tools",
    "desk organizer",
    "air fryer accessories",
    "camping gear",
    "phone holder car",
    "mini projector",
    "robot vacuum accessories",
    "security camera",
    "electric toothbrush",
    "hair clipper",
    "drone accessories",
    "tablet stand",
    "water bottle",
    "travel accessories",
]

SEARCH_STRATEGIES = [
    {"sort": "LAST_VOLUME_DESC", "name": "best_sellers"},
    {"sort": "COMMISSION_RATE_DESC", "name": "high_commission"},
    {"sort": "SALE_PRICE_ASC", "name": "cheapest_deals"},
]

_IMAGE_DIR = Path("data/images")


class HotProductFetcher:
    def __init__(
        self,
        ali_api,
        rewriter: ContentRewriter,
        image_processor,
        session: Session,
        router: DestinationRouter,
        category_resolver: CategoryResolver,
        affiliate_pool: AffiliateLinkPool | None,
        max_products_per_run: int = 3,
    ) -> None:
        self._api = ali_api
        self._rewriter = rewriter
        self._image_processor = image_processor
        self._session = session
        self._router = router
        self._category_resolver = category_resolver
        self._affiliate_pool = affiliate_pool
        self._max_per_run = max_products_per_run

    async def fetch_and_queue(self) -> int:
        if not self._api.is_enabled:
            logger.debug("AliExpress API not enabled, skipping hot products")
            return 0

        query = SEARCH_QUERIES[hash(datetime.date.today().isoformat()) % len(SEARCH_QUERIES)]
        strategy = SEARCH_STRATEGIES[hash(query) % len(SEARCH_STRATEGIES)]
        logger.info(f"Fetching hot products: '{query}' strategy={strategy['name']}")

        try:
            products = self._api.search_products(
                keywords=query,
                min_sale_price=100,
                max_sale_price=3000,
                page_size=10,
                sort=strategy["sort"],
            )
        except Exception as e:
            logger.error(f"Failed to fetch hot products: {e}")
            return 0

        if not products:
            logger.warning(f"No products found for query: '{query}'")
            return 0

        queued = 0
        for product in products:
            if queued >= self._max_per_run:
                break

            product_id = str(getattr(product, "product_id", "") or "")
            if not product_id:
                continue

            existing = self._session.query(Deal).filter_by(product_id=product_id).first()
            if existing:
                logger.debug(f"Hot product {product_id} already queued, skipping")
                continue

            try:
                deal = await self._process_product(product)
                if deal:
                    queued += 1
            except Exception as e:
                logger.error(f"Failed to process hot product {product_id}: {e}")

        logger.info(f"Hot products run complete: {queued} queued from query '{query}'")
        return queued

    async def _process_product(self, product: object) -> Optional[Deal]:
        product_id = str(getattr(product, "product_id", "") or "")
        title = str(getattr(product, "product_title", "") or "Unknown Product")
        sale_price = float(getattr(product, "target_sale_price", 0) or 0)
        original_price = float(getattr(product, "target_original_price", 0) or 0)
        orders = int(getattr(product, "lastest_volume", 0) or 0)
        discount = str(getattr(product, "discount", "") or "")
        image_url = str(getattr(product, "product_main_image_url", "") or "")
        ali_category_raw = str(getattr(product, "first_level_category_name", "") or "") or None
        product_url = f"https://www.aliexpress.com/item/{product_id}.html"

        affiliate_link = None
        affiliate_account_key = None
        if self._affiliate_pool:
            affiliate_link, affiliate_account_key = self._affiliate_pool.get_affiliate_link(
                product_url,
                seed=product_id,
            )
        if not affiliate_link:
            affiliate_link = str(getattr(product, "promotion_link", "") or "") or None
        if not affiliate_link:
            logger.warning(f"No promotion link for product {product_id}, skipping")
            return None

        text_hash = hashlib.md5(product_id.encode()).hexdigest()
        category_resolution = await self._category_resolver.resolve(
            product_name=title,
            original_text=f"{title}\nOrders: {orders}\nDiscount: {discount}",
            ali_category_raw=ali_category_raw,
        )

        rewrite_result = await self._rewriter.rewrite(
            product_name=title,
            price=sale_price,
            currency="USD",
            shipping=None,
            original_text=(
                f"{title}\n"
                f"Original: ${original_price} -> Sale: ${sale_price}\n"
                f"Orders: {orders}\n"
                f"Discount: {discount}"
            ),
            rating=None,
            sales_count=orders,
            usd_ils_rate=get_cached_rate(),
        )

        image_path: Optional[str] = None
        image_hash: Optional[str] = None
        if image_url:
            img_bytes = _download_image(image_url)
            if img_bytes:
                try:
                    image_hash = compute_image_hash(img_bytes)
                    watermarked = self._image_processor.add_watermark(img_bytes)
                    _IMAGE_DIR.mkdir(parents=True, exist_ok=True)
                    tmp = tempfile.NamedTemporaryFile(
                        dir=str(_IMAGE_DIR), suffix=".jpg", delete=False
                    )
                    tmp.write(watermarked)
                    tmp.close()
                    image_path = tmp.name
                except Exception as e:
                    logger.warning(f"Image processing failed for {product_id}: {e}")

        raw = RawMessage(
            source_group="hot_products",
            telegram_message_id=0,
            raw_text=f"[Hot Product] {title}",
            has_images=bool(image_url),
            received_at=datetime.datetime.now(datetime.UTC),
            status="processed",
        )
        self._session.add(raw)
        self._session.flush()

        deal = Deal(
            raw_message_id=raw.id,
            product_id=product_id,
            product_name=rewrite_result.product_name_clean,
            original_text=f"[Hot Product] {title}",
            rewritten_text=rewrite_result.rewritten_text,
            price=sale_price,
            original_price=original_price if original_price > sale_price else None,
            currency="USD",
            category=category_resolution.category,
            ali_category_raw=category_resolution.ali_category_raw,
            category_source=category_resolution.source,
            affiliate_account_key=affiliate_account_key,
            affiliate_link=affiliate_link,
            product_link=product_url,
            image_hash=image_hash,
            image_path=image_path,
            text_hash=text_hash,
            source_group="hot_products",
            created_at=datetime.datetime.now(datetime.UTC),
        )
        self._session.add(deal)
        self._session.flush()

        if image_path:
            new_path = _IMAGE_DIR / f"{deal.id}.jpg"
            Path(image_path).rename(new_path)
            deal.image_path = str(new_path)

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

        logger.info(
            f"Hot product queued: {title[:50]!r} "
            f"(${sale_price}, category={category_resolution.category}, destinations={len(destinations)})"
        )
        return deal


def _download_image(url: str) -> Optional[bytes]:
    try:
        response = httpx.get(
            url,
            timeout=15.0,
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error(f"Failed to download image from {url}: {e}")
        return None
