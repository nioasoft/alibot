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


def _safe_int(value) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _as_optional_str(value) -> Optional[str]:
    if value in (None, ""):
        return None
    value = str(value).strip()
    return value or None


def _safe_bool_flag(value) -> Optional[bool]:
    normalized = _as_optional_str(value)
    if normalized is None:
        return None
    normalized = normalized.upper()
    if normalized == "Y":
        return True
    if normalized == "N":
        return False
    return None


@dataclass
class ProductDetails:
    title: str
    price: float
    sale_price: Optional[float]
    app_sale_price: Optional[float]
    currency: str
    images: list[str]  # HD image URLs
    rating: Optional[float]
    orders_count: Optional[int]
    commission_rate: Optional[float]
    category: Optional[str]
    promo_codes: list["PromoCode"]


@dataclass
class AffiliateOrder:
    order_id: str
    sub_order_id: Optional[str]
    order_status: Optional[str]
    tracking_id: Optional[str]
    custom_parameters: Optional[str]
    product_id: Optional[str]
    product_title: Optional[str]
    product_detail_url: Optional[str]
    product_main_image_url: Optional[str]
    product_count: Optional[int]
    ship_to_country: Optional[str]
    settled_currency: Optional[str]
    paid_amount: Optional[float]
    finished_amount: Optional[float]
    estimated_paid_commission: Optional[float]
    estimated_finished_commission: Optional[float]
    commission_rate: Optional[float]
    incentive_commission_rate: Optional[float]
    new_buyer_bonus_commission: Optional[float]
    is_new_buyer: Optional[bool]
    order_type: Optional[str]
    order_platform: Optional[str]
    effect_detail_status: Optional[str]
    category_id: Optional[int]
    created_time: Optional[str]
    paid_time: Optional[str]
    finished_time: Optional[str]
    completed_settlement_time: Optional[str]
    raw_payload: dict


@dataclass(frozen=True)
class PromoCode:
    code: str
    value: Optional[str] = None
    minimum_spend: Optional[str] = None
    promotion_url: Optional[str] = None


def extract_promo_codes(raw) -> list[PromoCode]:
    if not raw:
        return []

    items = raw if isinstance(raw, (list, tuple)) else [raw]
    promo_codes: list[PromoCode] = []
    seen: set[str] = set()

    for item in items:
        code = getattr(item, "promo_code", None) or getattr(item, "code", None)
        if not code:
            continue
        code = str(code).strip().upper()
        if not code or code in seen:
            continue
        seen.add(code)
        promo_codes.append(
            PromoCode(
                code=code,
                value=(str(getattr(item, "code_value", "")).strip() or None),
                minimum_spend=(str(getattr(item, "code_mini_spend", "")).strip() or None),
                promotion_url=(str(getattr(item, "code_promotionurl", "")).strip() or None),
            )
        )

    return promo_codes


def select_best_sale_price(
    sale_price: Optional[float],
    app_sale_price: Optional[float],
) -> Optional[float]:
    prices = [price for price in (sale_price, app_sale_price) if price and price > 0]
    if not prices:
        return None
    return min(prices)


class AliExpressClient:
    def __init__(
        self,
        app_key: str,
        app_secret: str,
        tracking_id: str,
        account_key: str = "primary",
        require_tracking_id: bool = True,
        country: str = "IL",
    ):
        self.account_key = account_key
        self._require_tracking_id = require_tracking_id
        self._country = country
        self._enabled = bool(app_key and app_secret and (tracking_id or not require_tracking_id))

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
                    f"AliExpress API credentials not configured for account '{self.account_key}'"
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
                logger.warning(
                    f"No affiliate link for {product_url} on account '{self.account_key}': {msg}"
                )
                return None
            logger.warning(f"No affiliate link returned for {product_url} on account '{self.account_key}'")
            return None
        except Exception as e:
            logger.error(f"Failed to generate affiliate link on account '{self.account_key}': {e}")
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
            products = self._api.get_products_details([product_id], country=self._country)
            if not products or len(products) == 0:
                logger.warning(f"No product found for ID {product_id} on account '{self.account_key}'")
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
                app_sale_price=float(getattr(p, "target_app_sale_price", 0) or 0) or None,
                currency=getattr(p, "target_original_price_currency", "ILS"),
                images=images,
                rating=_safe_float(getattr(p, "evaluate_rate", 0)),
                orders_count=int(getattr(p, "lastest_volume", 0) or 0) or None,
                commission_rate=_safe_float(getattr(p, "commission_rate", 0)),
                category=getattr(p, "first_level_category_name", None),
                promo_codes=extract_promo_codes(
                    getattr(p, "promo_code_info", None) or getattr(p, "promoCodeInfo", None)
                ),
            )
        except Exception as e:
            logger.error(
                f"Failed to get product details for {product_id} on account '{self.account_key}': {e}"
            )
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
                ship_to_country=self._country,
                sort=sort,
            )
            if result and hasattr(result, "products") and result.products:
                return result.products
            return []
        except Exception as e:
            logger.error(f"Product search failed for '{keywords}' on account '{self.account_key}': {e}")
            return []

    def get_orders(
        self,
        status: str,
        start_time: str,
        end_time: str,
        page_no: int = 1,
        page_size: int = 50,
        locale_site: str = "global",
    ) -> tuple[list[AffiliateOrder], int]:
        if not self.is_enabled:
            return [], 0

        fields = [
            "order_id",
            "sub_order_id",
            "order_status",
            "tracking_id",
            "custom_parameters",
            "product_id",
            "product_title",
            "product_detail_url",
            "product_main_image_url",
            "product_count",
            "ship_to_country",
            "settled_currency",
            "paid_amount",
            "finished_amount",
            "estimated_paid_commission",
            "estimated_finished_commission",
            "commission_rate",
            "incentive_commission_rate",
            "new_buyer_bonus_commission",
            "is_new_buyer",
            "order_type",
            "order_platform",
            "effect_detail_status",
            "category_id",
            "created_time",
            "paid_time",
            "finished_time",
            "completed_settlement_time",
        ]

        try:
            response = self._api.get_order_list(
                status=status,
                start_time=start_time,
                end_time=end_time,
                fields=fields,
                locale_site=locale_site,
                page_no=page_no,
                page_size=page_size,
            )
        except Exception as e:
            if "No orders found" in str(e):
                return [], 0
            logger.error(
                f"Failed to fetch affiliate orders on account '{self.account_key}' "
                f"status='{status}' page={page_no}: {e}"
            )
            return [], 0

        raw_orders = getattr(response, "orders", None)
        if raw_orders is None:
            orders = []
        elif isinstance(raw_orders, list):
            orders = raw_orders
        elif hasattr(raw_orders, "order"):
            nested = getattr(raw_orders, "order", None)
            if nested is None:
                orders = []
            elif isinstance(nested, list):
                orders = nested
            else:
                orders = [nested]
        else:
            orders = [raw_orders]
        total_pages = int(getattr(response, "total_page_no", 0) or 0)
        return [self._parse_affiliate_order(order) for order in orders], total_pages

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

    def _parse_affiliate_order(self, order: object) -> AffiliateOrder:
        raw_payload = {
            key: getattr(order, key)
            for key in dir(order)
            if not key.startswith("_") and not callable(getattr(order, key))
        }
        return AffiliateOrder(
            order_id=str(getattr(order, "order_id", "") or ""),
            sub_order_id=_as_optional_str(getattr(order, "sub_order_id", None)),
            order_status=_as_optional_str(getattr(order, "order_status", None)),
            tracking_id=_as_optional_str(getattr(order, "tracking_id", None)),
            custom_parameters=_as_optional_str(
                getattr(order, "custom_parameters", None)
                or getattr(order, "customer_parameters", None)
            ),
            product_id=_as_optional_str(getattr(order, "product_id", None)),
            product_title=_as_optional_str(getattr(order, "product_title", None)),
            product_detail_url=_as_optional_str(getattr(order, "product_detail_url", None)),
            product_main_image_url=_as_optional_str(
                getattr(order, "product_main_image_url", None)
            ),
            product_count=_safe_int(getattr(order, "product_count", None)),
            ship_to_country=_as_optional_str(getattr(order, "ship_to_country", None)),
            settled_currency=_as_optional_str(getattr(order, "settled_currency", None)),
            paid_amount=_safe_float(getattr(order, "paid_amount", None)),
            finished_amount=_safe_float(getattr(order, "finished_amount", None)),
            estimated_paid_commission=_safe_float(
                getattr(order, "estimated_paid_commission", None)
            ),
            estimated_finished_commission=_safe_float(
                getattr(order, "estimated_finished_commission", None)
            ),
            commission_rate=_safe_float(getattr(order, "commission_rate", None)),
            incentive_commission_rate=_safe_float(
                getattr(order, "incentive_commission_rate", None)
            ),
            new_buyer_bonus_commission=_safe_float(
                getattr(order, "new_buyer_bonus_commission", None)
            ),
            is_new_buyer=_safe_bool_flag(getattr(order, "is_new_buyer", None)),
            order_type=_as_optional_str(getattr(order, "order_type", None)),
            order_platform=_as_optional_str(getattr(order, "order_platform", None)),
            effect_detail_status=_as_optional_str(
                getattr(order, "effect_detail_status", None)
            ),
            category_id=_safe_int(getattr(order, "category_id", None)),
            created_time=_as_optional_str(getattr(order, "created_time", None)),
            paid_time=_as_optional_str(getattr(order, "paid_time", None)),
            finished_time=_as_optional_str(getattr(order, "finished_time", None)),
            completed_settlement_time=_as_optional_str(
                getattr(order, "completed_settlement_time", None)
            ),
            raw_payload=raw_payload,
        )
