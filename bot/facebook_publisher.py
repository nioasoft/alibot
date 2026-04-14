"""Facebook publisher adapter backed by the local Playwright service."""

from __future__ import annotations

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
        landing_url = self._landing_url_for(deal)
        text = deal.rewritten_text
        if landing_url:
            text += f"\n\n🌐 להצטרפות לכל הקבוצות: {landing_url}"
        return text

    def _build_append_text(self, deal: Deal) -> str:
        purchase_url = deal.affiliate_link or deal.product_link
        return f"\n\n🛒 לרכישה: {purchase_url}"

    async def send_deal(self, deal: Deal, group_url: str) -> bool:
        if not self._enabled:
            logger.warning("Facebook publisher is disabled")
            return False

        payload = {
            "group_url": group_url,
            "text": self._build_primary_text(deal),
            "append_text": self._build_append_text(deal),
            "dry_run": False,
        }

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(f"{self._service_url}/publish", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    return bool(data.get("ok"))

                logger.error(f"Facebook send failed: {resp.status_code} {resp.text}")
                return False
        except httpx.ConnectError:
            logger.warning("Facebook service not running")
            return False
        except Exception as e:
            logger.error(f"Facebook send error: {e}")
            return False
