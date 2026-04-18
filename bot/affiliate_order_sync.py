"""Sync AliExpress affiliate orders into Supabase for conversion analytics."""

from __future__ import annotations

import datetime
import json
from typing import Iterable

from loguru import logger
from supabase import create_client

from bot.aliexpress_client import AffiliateOrder, AliExpressClient
from bot.category_mapper import map_aliexpress_category

ORDER_STATUSES = ("Payment Completed", "Buyer Confirmed Receipt")
MAX_ALIEXPRESS_CATEGORY_LOOKUPS = 100


class AffiliateOrderSync:
    def __init__(
        self,
        clients: dict[str, AliExpressClient],
        url: str,
        key: str,
        product_details_client: object | None = None,
        lookback_days: int = 30,
        page_size: int = 50,
        locale_site: str = "global",
    ) -> None:
        self._clients = clients
        self._client = create_client(url, key)
        self._product_details_client = product_details_client
        self._lookback_days = lookback_days
        self._page_size = page_size
        self._locale_site = locale_site

    @property
    def is_enabled(self) -> bool:
        return bool(self._enabled_clients())

    async def sync_recent_orders(self) -> dict[str, int]:
        if not self.is_enabled:
            logger.debug("Affiliate order sync disabled; no enabled affiliate accounts")
            return {"orders": 0, "accounts": 0}
        try:
            now = datetime.datetime.now(datetime.UTC)
            start_time = (now - datetime.timedelta(days=self._lookback_days)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            end_time = now.strftime("%Y-%m-%d %H:%M:%S")

            all_rows: list[dict] = []
            enabled_clients = self._enabled_clients()

            for account_key, client in enabled_clients.items():
                for status in ORDER_STATUSES:
                    rows = self._fetch_all_orders_for_status(
                        client=client,
                        account_key=account_key,
                        status=status,
                        start_time=start_time,
                        end_time=end_time,
                    )
                    if rows:
                        all_rows.extend(rows)

            if not all_rows:
                logger.info("Affiliate order sync complete: no orders returned")
                return {"orders": 0, "accounts": len(enabled_clients)}

            category_map = self._fetch_category_map(
                [
                    row["product_id"]
                    for row in all_rows
                    if row.get("product_id")
                ]
            )

            synced_at = now.isoformat()
            for row in all_rows:
                row["resolved_category"] = category_map.get(row.get("product_id"))
                row["synced_at"] = synced_at

            for chunk in _chunked(all_rows, 200):
                self._client.table("affiliate_orders").upsert(
                    chunk, on_conflict="order_key"
                ).execute()

            logger.info(
                f"Affiliate order sync complete: upserted {len(all_rows)} rows "
                f"across {len(enabled_clients)} accounts"
            )
            return {"orders": len(all_rows), "accounts": len(enabled_clients)}
        except Exception as exc:
            logger.error(f"Affiliate order sync failed: {exc}")
            return {"orders": 0, "accounts": len(self._enabled_clients())}

    def _fetch_all_orders_for_status(
        self,
        client: AliExpressClient,
        account_key: str,
        status: str,
        start_time: str,
        end_time: str,
    ) -> list[dict]:
        rows: list[dict] = []
        page_no = 1

        while True:
            orders, total_pages = client.get_orders(
                status=status,
                start_time=start_time,
                end_time=end_time,
                page_no=page_no,
                page_size=self._page_size,
                locale_site=self._locale_site,
            )
            if not orders:
                break

            rows.extend(self._build_order_rows(account_key, order) for order in orders)

            if total_pages <= page_no:
                break
            page_no += 1

        return rows

    def _fetch_category_map(self, product_ids: Iterable[str]) -> dict[str, str]:
        ids = [product_id for product_id in dict.fromkeys(product_ids) if product_id]
        if not ids:
            return {}

        category_map = self._fetch_deal_category_map(ids)
        missing_ids = [product_id for product_id in ids if product_id not in category_map]
        if missing_ids:
            category_map.update(self._fetch_tracking_link_category_map(missing_ids))

        still_missing = [product_id for product_id in ids if product_id not in category_map]
        if still_missing:
            category_map.update(self._fetch_aliexpress_category_map(still_missing))

        return category_map

    def _fetch_deal_category_map(self, product_ids: Iterable[str]) -> dict[str, str]:
        category_map: dict[str, str] = {}
        try:
            for chunk in _chunked(list(product_ids), 200):
                result = (
                    self._client.table("deals")
                    .select("product_id, category")
                    .in_("product_id", chunk)
                    .execute()
                )
                for row in result.data or []:
                    product_id = str(row.get("product_id", "")).strip()
                    category = str(row.get("category", "")).strip()
                    if product_id and category:
                        category_map[product_id] = category
        except Exception as exc:
            logger.warning(f"Failed to resolve order categories from deals table: {exc}")
        return category_map

    def _fetch_tracking_link_category_map(self, product_ids: Iterable[str]) -> dict[str, str]:
        wanted_ids = {product_id for product_id in product_ids if product_id}
        if not wanted_ids:
            return {}

        category_map: dict[str, str] = {}
        try:
            result = (
                self._client.table("tracking_links")
                .select("metadata")
                .order("created_at", desc=True)
                .limit(5000)
                .execute()
            )
            for row in result.data or []:
                metadata = _coerce_metadata(row.get("metadata"))
                product_id = str(metadata.get("product_id", "")).strip()
                category = str(metadata.get("category", "")).strip()
                if product_id in wanted_ids and category and product_id not in category_map:
                    category_map[product_id] = category
        except Exception as exc:
            logger.warning(f"Failed to resolve order categories from tracking links: {exc}")
        return category_map

    def _fetch_aliexpress_category_map(self, product_ids: Iterable[str]) -> dict[str, str]:
        client = self._product_details_client
        if client is None or not getattr(client, "is_enabled", False):
            client = next(iter(self._enabled_clients().values()), None)
        if client is None:
            return {}

        category_map: dict[str, str] = {}
        for product_id in list(dict.fromkeys(product_ids))[:MAX_ALIEXPRESS_CATEGORY_LOOKUPS]:
            details = client.get_product_details(product_id)
            if details is None:
                continue
            category = map_aliexpress_category(details.category)
            if category:
                category_map[product_id] = category
        return category_map

    def _build_order_rows(self, account_key: str, order: AffiliateOrder) -> dict:
        identity = order.sub_order_id or order.order_id
        return {
            "order_key": f"{account_key}:{identity}",
            "account_key": account_key,
            "order_id": order.order_id,
            "sub_order_id": order.sub_order_id,
            "order_status": order.order_status,
            "tracking_id": order.tracking_id,
            "custom_parameters": order.custom_parameters,
            "product_id": order.product_id,
            "product_title": order.product_title,
            "product_detail_url": order.product_detail_url,
            "product_main_image_url": order.product_main_image_url,
            "product_count": order.product_count,
            "ship_to_country": order.ship_to_country,
            "settled_currency": order.settled_currency,
            "paid_amount": order.paid_amount,
            "finished_amount": order.finished_amount,
            "estimated_paid_commission": order.estimated_paid_commission,
            "estimated_finished_commission": order.estimated_finished_commission,
            "commission_rate": order.commission_rate,
            "incentive_commission_rate": order.incentive_commission_rate,
            "new_buyer_bonus_commission": order.new_buyer_bonus_commission,
            "is_new_buyer": order.is_new_buyer,
            "order_type": order.order_type,
            "order_platform": order.order_platform,
            "effect_detail_status": order.effect_detail_status,
            "category_id": order.category_id,
            "created_time": order.created_time,
            "paid_time": order.paid_time,
            "finished_time": order.finished_time,
            "completed_settlement_time": order.completed_settlement_time,
            "raw_payload": order.raw_payload,
        }

    def _enabled_clients(self) -> dict[str, AliExpressClient]:
        return {
            key: client
            for key, client in self._clients.items()
            if getattr(client, "is_enabled", False)
        }


def _chunked(items: list, size: int) -> list[list]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def _coerce_metadata(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}
    return {}
