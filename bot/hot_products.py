"""Auto-fetch and publish trending AliExpress products."""

from __future__ import annotations

import datetime
import hashlib
import random
import tempfile
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger
from sqlalchemy.orm import Session

from bot.image_processor import compute_image_hash
from bot.models import Deal, PublishQueueItem, RawMessage
from bot.rewriter import ContentRewriter, RewriteResult

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

# Search strategies: rotate between different sort methods
SEARCH_STRATEGIES = [
    {"sort": "LAST_VOLUME_DESC", "name": "best_sellers"},      # Most popular
    {"sort": "COMMISSION_RATE_DESC", "name": "high_commission"}, # Best commission
    {"sort": "SALE_PRICE_ASC", "name": "cheapest_deals"},       # Cheapest (impulse buys)
]

# Maps AliExpress top-level categories to our internal ones
_CATEGORY_MAP: dict[str, str] = {
    "Consumer Electronics": "tech",
    "Phones & Telecommunications": "tech",
    "Computer & Office": "tech",
    "Home & Garden": "home",
    "Home Improvement": "home",
    "Women's Clothing": "fashion",
    "Men's Clothing": "fashion",
    "Shoes": "fashion",
    "Jewelry & Accessories": "fashion",
    "Beauty & Health": "beauty",
    "Toys & Hobbies": "toys",
    "Sports & Entertainment": "sports",
    "Automobiles & Motorcycles": "auto",
    "Mother & Kids": "toys",
}

_IMAGE_DIR = Path("data/images")


class HotProductFetcher:
    """Fetches trending AliExpress products and enqueues them for publishing.

    Periodically picks a random search query, fetches products via the
    AliExpress Affiliate API, rewrites each one in Hebrew, watermarks the
    image, and inserts a Deal + PublishQueueItem into the database.
    """

    def __init__(
        self,
        ali_api,
        rewriter: ContentRewriter,
        image_processor,
        session: Session,
        target_groups: dict[str, str],
        channel_link: str = "",
        max_products_per_run: int = 3,
    ) -> None:
        self._api = ali_api
        self._rewriter = rewriter
        self._image_processor = image_processor
        self._session = session
        self._target_groups = target_groups
        self._channel_link = channel_link
        self._max_per_run = max_products_per_run

    async def fetch_and_queue(self) -> int:
        """Fetch hot products and add to publish queue.

        Rotates between strategies: best sellers, high commission, cheapest deals.

        Returns:
            Number of products successfully queued.
        """
        if not self._api.is_enabled:
            logger.debug("AliExpress API not enabled, skipping hot products")
            return 0

        query = random.choice(SEARCH_QUERIES)
        strategy = random.choice(SEARCH_STRATEGIES)
        logger.info(f"Fetching hot products: '{query}' strategy={strategy['name']}")

        try:
            products = self._api.search_products(
                keywords=query,
                min_sale_price=100,   # $1
                max_sale_price=3000,  # $30
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

            # Skip if already in the database
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
                continue

        logger.info(f"Hot products run complete: {queued} queued from query '{query}'")
        return queued

    async def _process_product(self, product: object) -> Optional[Deal]:
        """Process a single product: rewrite, watermark, save, enqueue.

        Args:
            product: A product object returned by the AliExpress API.

        Returns:
            The created Deal, or None if processing was skipped/failed.
        """
        product_id = str(getattr(product, "product_id", "") or "")
        title = str(getattr(product, "product_title", "") or "Unknown Product")
        sale_price = float(getattr(product, "target_sale_price", 0) or 0)
        original_price = float(getattr(product, "target_original_price", 0) or 0)
        commission = str(getattr(product, "commission_rate", "") or "")
        orders = int(getattr(product, "lastest_volume", 0) or 0)
        # get_products returns very long promotion_links (800+ chars)
        # Use get_affiliate_links instead for short URLs
        product_url = f"https://www.aliexpress.com/item/{product_id}.html"
        promo_link = self._api.get_affiliate_link(product_url) or str(getattr(product, "promotion_link", "") or "")
        image_url = str(getattr(product, "product_main_image_url", "") or "")
        category = str(getattr(product, "first_level_category_name", "") or "other")
        discount = str(getattr(product, "discount", "") or "")

        if not promo_link:
            logger.warning(f"No promotion link for product {product_id}, skipping")
            return None

        # Build a text hash based on the product ID for dedup
        text_hash = hashlib.md5(product_id.encode()).hexdigest()

        # AI rewrite (Hebrew post)
        original_text = (
            f"{title}\n"
            f"Original: ${original_price} → Sale: ${sale_price}\n"
            f"Orders: {orders}\n"
            f"Discount: {discount}"
        )
        rewrite_result: RewriteResult = await self._rewriter.rewrite(
            product_name=title,
            price=sale_price,
            currency="USD",
            shipping=None,
            original_text=original_text,
            rating=None,
            sales_count=orders,
        )

        # Download and watermark image
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

        # Synthetic raw message for traceability
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

        mapped_category = _CATEGORY_MAP.get(category, rewrite_result.category)

        deal = Deal(
            raw_message_id=raw.id,
            product_id=product_id,
            product_name=rewrite_result.product_name_clean,
            original_text=f"[Hot Product] {title}",
            rewritten_text=rewrite_result.rewritten_text,
            price=sale_price,
            original_price=original_price if original_price > sale_price else None,
            currency="USD",
            category=mapped_category,
            affiliate_link=promo_link,
            product_link=f"https://www.aliexpress.com/item/{product_id}.html",
            image_hash=image_hash,
            image_path=image_path,
            text_hash=text_hash,
            source_group="hot_products",
            created_at=datetime.datetime.now(datetime.UTC),
        )
        self._session.add(deal)
        self._session.flush()

        # Rename temp image to use deal.id for consistency with the pipeline
        if image_path:
            new_path = _IMAGE_DIR / f"{deal.id}.jpg"
            Path(image_path).rename(new_path)
            deal.image_path = str(new_path)

        # Resolve target group
        target = self._target_groups.get(mapped_category) or self._target_groups.get("default", "")

        queue_item = PublishQueueItem(
            deal_id=deal.id,
            target_group=target,
            status="queued",
            scheduled_after=datetime.datetime.now(datetime.UTC),
        )
        self._session.add(queue_item)
        self._session.commit()

        logger.info(
            f"Hot product queued: {title[:50]!r} "
            f"(${sale_price}, commission={commission}, category={mapped_category})"
        )
        return deal


def _download_image(url: str) -> Optional[bytes]:
    """Download an image from a URL.

    Args:
        url: The image URL to download.

    Returns:
        Raw image bytes, or None on failure.
    """
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
