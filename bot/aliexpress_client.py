"""AliExpress Affiliate API client for product details and affiliate links."""

from __future__ import annotations

from typing import Optional
from dataclasses import dataclass

from loguru import logger

try:
    from aliexpress_api import AliexpressApi, models as ali_models
    HAS_ALI_API = True
except ImportError:
    HAS_ALI_API = False


def _safe_float(value) -> Optional[float]:
    """Parse float from API values like '96.2%' or '7.0'."""
    if not value:
        return None
    try:
        return float(str(value).rstrip("%"))
    except (ValueError, TypeError):
        return None


@dataclass
class ProductDetails:
    title: str
    price: float
    sale_price: Optional[float]
    currency: str
    images: list[str]  # HD image URLs
    rating: Optional[float]
    orders_count: Optional[int]
    commission_rate: Optional[float]
    category: Optional[str]


class AliExpressClient:
    def __init__(self, app_key: str, app_secret: str, tracking_id: str, account_key: str = "primary"):
        self.account_key = account_key
        self._enabled = bool(app_key and app_secret and tracking_id)

        if self._enabled and HAS_ALI_API:
            self._api = AliexpressApi(
                app_key,
                app_secret,
                ali_models.Language.EN,
                ali_models.Currency.USD,
                tracking_id,
            )
            logger.info(f"AliExpress API client initialized for account '{self.account_key}'")
        else:
            self._api = None
            if not self._enabled:
                logger.warning(
                    "AliExpress API credentials not configured — affiliate links disabled"
                )
            elif not HAS_ALI_API:
                logger.warning(
                    "python-aliexpress-api not installed — run: pip install python-aliexpress-api"
                )

    @property
    def is_enabled(self) -> bool:
        return self._enabled and self._api is not None

    def get_affiliate_link(self, product_url: str) -> Optional[str]:
        """Generate affiliate link for a product URL.

        Args:
            product_url: The original product URL to convert to an affiliate link.

        Returns:
            Affiliate promotion link, or None if unavailable.
        """
        if not self.is_enabled:
            return None

        try:
            links = self._api.get_affiliate_links(product_url)
            if links and len(links) > 0:
                result = links[0]
                promo = getattr(result, "promotion_link", None)
                if promo:
                    logger.debug(f"Affiliate link generated: {str(promo)[:50]}...")
                    return str(promo)
                msg = getattr(result, "message", "unknown reason")
                logger.warning(f"No affiliate link for {product_url}: {msg}")
                return None
            logger.warning(f"No affiliate link returned for: {product_url}")
            return None
        except Exception as e:
            logger.error(f"Failed to generate affiliate link: {e}")
            return None

    def get_product_details(self, product_id: str) -> Optional[ProductDetails]:
        """Fetch product details including HD images.

        Args:
            product_id: The AliExpress product ID.

        Returns:
            ProductDetails dataclass, or None if unavailable.
        """
        if not self.is_enabled:
            return None

        try:
            products = self._api.get_products_details([product_id])
            if not products or len(products) == 0:
                logger.warning(f"No product found for ID: {product_id}")
                return None

            p = products[0]

            # Extract images
            images: list[str] = []
            if hasattr(p, "product_main_image_url") and p.product_main_image_url:
                images.append(p.product_main_image_url)
            if hasattr(p, "product_small_image_urls") and p.product_small_image_urls:
                if hasattr(p.product_small_image_urls, "string"):
                    images.extend(p.product_small_image_urls.string[:4])

            return ProductDetails(
                title=getattr(p, "product_title", ""),
                price=float(getattr(p, "target_original_price", 0) or 0),
                sale_price=float(getattr(p, "target_sale_price", 0) or 0) or None,
                currency=getattr(p, "target_original_price_currency", "ILS"),
                images=images,
                rating=_safe_float(getattr(p, "evaluate_rate", 0)),
                orders_count=int(getattr(p, "lastest_volume", 0) or 0) or None,
                commission_rate=_safe_float(getattr(p, "commission_rate", 0)),
                category=getattr(p, "first_level_category_name", None),
            )
        except Exception as e:
            logger.error(f"Failed to get product details for {product_id}: {e}")
            return None

    def search_products(
        self,
        keywords: str,
        min_sale_price: int = 100,
        max_sale_price: int = 5000,
        page_size: int = 10,
        sort: str = "SALE_PRICE_ASC",
    ) -> list:
        """Search for affiliate products by keyword.

        Args:
            keywords: Search keywords (e.g. 'bluetooth earbuds').
            min_sale_price: Minimum price in cents (100 = $1).
            max_sale_price: Maximum price in cents (5000 = $50).
            page_size: Number of results to return (max 50).
            sort: Sort order for results.

        Returns:
            List of product objects, empty list on failure or when disabled.
        """
        if not self.is_enabled:
            return []

        try:
            result = self._api.get_products(
                keywords=keywords,
                min_sale_price=min_sale_price,
                max_sale_price=max_sale_price,
                page_size=page_size,
                sort=sort,
            )
            if result and hasattr(result, "products") and result.products:
                return result.products
            return []
        except Exception as e:
            logger.error(f"Product search failed for '{keywords}': {e}")
            return []

    def download_image(self, image_url: str) -> Optional[bytes]:
        """Download product image from AliExpress CDN.

        Args:
            image_url: URL of the product image to download.

        Returns:
            Raw image bytes, or None if download failed.
        """
        import httpx

        try:
            response = httpx.get(
                image_url,
                timeout=15.0,
                headers={"User-Agent": "Mozilla/5.0"},
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Failed to download image {image_url}: {e}")
            return None
