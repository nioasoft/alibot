"""Facebook publisher adapter backed by the local Playwright service."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import httpx
from loguru import logger

from bot.models import Deal


class FacebookPublisher:
    def __init__(self, service_url: str = "http://localhost:3002", site_url: str = ""):
        self._service_url = service_url
        self._site_url = site_url.rstrip("/")
        self._enabled = bool(service_url and site_url)

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    async def check_health(self) -> bool:
        if not self._enabled:
            return False

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._service_url}/health")
                resp.raise_for_status()
                data = resp.json()
                return data.get("status") == "ok" and bool(data.get("authReady"))
        except Exception:
            return False

    def _landing_url_for(self, deal: Deal) -> str:
        return self._site_url or ""

    def _build_primary_text(self, deal: Deal) -> str:
        return deal.rewritten_text

    def _build_append_text(self, deal: Deal, purchase_url: str | None = None) -> str:
        extra_lines: list[str] = []
        landing_url = self._landing_url_for(deal)
        if landing_url:
            extra_lines.append(f"🌐 להצטרפות לקבוצות לפי תחומי עניין: {landing_url}")

        purchase_url = purchase_url or deal.affiliate_link or deal.product_link
        if purchase_url:
            extra_lines.append(f"🛒 לרכישה: {purchase_url}")

        if not extra_lines:
            return ""
        return "\n\n" + "\n".join(extra_lines)

    def _image_path_for(self, deal: Deal) -> str:
        if not deal.image_path:
            return ""
        return str(Path(deal.image_path).resolve())

    async def send_deal(self, deal: Deal, group_url: str, purchase_url: str | None = None) -> bool:
        if not self._enabled:
            logger.warning("Facebook publisher is disabled")
            return False

        payload = {
            "group_url": group_url,
            "text": self._build_primary_text(deal),
            "image_path": self._image_path_for(deal),
            "append_text": self._build_append_text(deal, purchase_url=purchase_url),
            "dry_run": False,
        }

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(f"{self._service_url}/publish", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("imageUpload") == "failed":
                        logger.warning(
                            f"Facebook published deal {deal.id} without uploaded image; "
                            f"falling back to link-only post"
                        )
                    return bool(data.get("ok"))

                logger.error(f"Facebook send failed: {resp.status_code} {resp.text}")
                return False
        except httpx.ConnectError:
            logger.warning("Facebook service not running")
            return False
        except Exception as e:
            logger.error(f"Facebook send error: {e}")
            return False
