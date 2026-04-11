"""Publish deals to Supabase for the website. Replaces the WebPublisher stub."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from supabase import Client as SupabaseClient

    from bot.models import Deal


class SupabasePublisher:
    def __init__(self, url: str, key: str, bucket: str = "deal-images") -> None:
        from supabase import create_client

        self._client: SupabaseClient = create_client(url, key)
        self._bucket = bucket
        logger.info("SupabasePublisher initialized")

    @property
    def is_enabled(self) -> bool:
        return True

    async def send_deal(self, target_ref: str, deal: Deal) -> bool:
        """Upload deal image to Storage and upsert deal row to Supabase."""
        try:
            image_url = self._upload_image(deal)

            from bot.exchange_rate import get_cached_rate

            price_ils = None
            if deal.currency == "USD" and deal.price:
                price_ils = round(deal.price * get_cached_rate(), 2)
            elif deal.currency == "ILS" and deal.price:
                price_ils = deal.price

            row = {
                "product_id": deal.product_id,
                "product_name": deal.product_name,
                "rewritten_text": deal.rewritten_text,
                "price": float(deal.price) if deal.price else 0,
                "original_price": float(deal.original_price) if deal.original_price else None,
                "currency": deal.currency,
                "price_ils": price_ils,
                "category": deal.category or "other",
                "affiliate_link": deal.affiliate_link,
                "product_link": deal.product_link,
                "image_url": image_url,
                "is_active": True,
                "published_at": datetime.datetime.now(datetime.UTC).isoformat(),
            }

            self._client.table("deals").upsert(
                row, on_conflict="product_id"
            ).execute()

            logger.info(
                f"Published deal {deal.product_id} to Supabase (image: {bool(image_url)})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to publish deal {deal.product_id} to Supabase: {e}")
            return False

    def _upload_image(self, deal: Deal) -> str | None:
        """Upload watermarked image to Supabase Storage, return public URL."""
        if not deal.image_path:
            return None

        image_file = Path(deal.image_path)
        if not image_file.exists():
            logger.warning(f"Image file not found: {deal.image_path}")
            return None

        try:
            storage_path = f"{deal.product_id}.jpg"
            image_bytes = image_file.read_bytes()

            # Remove existing file if it exists (for upsert scenarios)
            try:
                self._client.storage.from_(self._bucket).remove([storage_path])
            except Exception:
                pass

            self._client.storage.from_(self._bucket).upload(
                storage_path,
                image_bytes,
                file_options={"content-type": "image/jpeg"},
            )

            public_url = self._client.storage.from_(self._bucket).get_public_url(
                storage_path
            )
            return public_url

        except Exception as e:
            logger.error(f"Failed to upload image for deal {deal.product_id}: {e}")
            return None

    async def cleanup_old_images(self, days: int = 7) -> None:
        """Delete images from Storage for deals older than the retention window.

        The database rows are cleaned up by pg_cron. This handles the
        corresponding Storage files.
        """
        try:
            cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=days)

            result = (
                self._client.table("deals")
                .select("product_id")
                .lt("published_at", cutoff.isoformat())
                .execute()
            )

            if not result.data:
                return

            paths = [f"{row['product_id']}.jpg" for row in result.data]
            self._client.storage.from_(self._bucket).remove(paths)
            logger.info(f"Cleaned up {len(paths)} old images from Supabase Storage")

        except Exception as e:
            logger.error(f"Failed to clean up old Supabase images: {e}")
