"""Facebook publisher adapter backed by the local Playwright service."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger

from bot.models import Deal

_STRUCTURED_PREFIXES = (
    "💰",
    "🚚",
    "🎟️",
    "🛒",
    "🌐",
)

_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)


class FacebookPublisher:
    def __init__(
        self,
        service_url: str = "http://localhost:3002",
        site_url: str = "",
        comment_on_post: bool = True,
    ):
        self._service_url = service_url
        self._site_url = site_url.rstrip("/")
        self._comment_on_post = comment_on_post
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

    @staticmethod
    def _normalize_lines(text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    @staticmethod
    def _looks_structured(line: str) -> bool:
        return line.startswith(_STRUCTURED_PREFIXES) or bool(_URL_PATTERN.search(line))

    @staticmethod
    def _shorten_line(line: str, max_length: int = 120) -> str:
        if len(line) <= max_length:
            return line
        return line[: max_length - 1].rstrip() + "…"

    def _build_compact_primary_text(self, deal: Deal) -> str:
        lines = self._normalize_lines(deal.rewritten_text)
        if not lines:
            return ""

        body_lines = [line for line in lines if not self._looks_structured(line)]
        if not body_lines:
            body_lines = lines[:2]

        compact_lines: list[str] = []
        for line in body_lines[:2]:
            shortened = self._shorten_line(line)
            if shortened not in compact_lines:
                compact_lines.append(shortened)

        if deal.price and deal.currency:
            amount = (
                f"₪{deal.price:.2f}".rstrip("0").rstrip(".")
                if deal.currency == "ILS"
                else f"${deal.price:.2f}".rstrip("0").rstrip(".")
                if deal.currency == "USD"
                else f"{deal.currency} {deal.price:.2f}".rstrip("0").rstrip(".")
            )
            compact_lines.append(f"מחיר: {amount}")

        if deal.shipping and deal.shipping.strip():
            shipping_text = self._shorten_line(deal.shipping.strip(), max_length=50)
            compact_lines.append(f"משלוח: {shipping_text}")

        return "\n".join(compact_lines[:4]).strip()

    def _build_primary_text(self, deal: Deal) -> str:
        if self._comment_on_post:
            compact = self._build_compact_primary_text(deal)
            if compact:
                return compact
        return deal.rewritten_text

    def _build_link_text(self, deal: Deal, purchase_url: str | None = None) -> str:
        extra_lines: list[str] = []
        landing_url = self._landing_url_for(deal)
        if landing_url and not self._comment_on_post:
            extra_lines.append(f"🌐 להצטרפות לקבוצות לפי תחומי עניין: {landing_url}")

        purchase_url = purchase_url or deal.affiliate_link or deal.product_link
        if purchase_url:
            if self._comment_on_post:
                extra_lines.append(f"🛒 קישור לרכישה: {purchase_url}")
            else:
                extra_lines.append(f"🛒 לרכישה: {purchase_url}")

        if not extra_lines:
            return ""
        return "\n".join(extra_lines)

    def _build_append_text(self, deal: Deal, purchase_url: str | None = None) -> str:
        link_text = self._build_link_text(deal, purchase_url=purchase_url)
        if not link_text:
            return ""
        return "\n\n" + link_text

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
            "append_text": (
                ""
                if self._comment_on_post
                else self._build_append_text(deal, purchase_url=purchase_url)
            ),
            "comment_text": (
                self._build_link_text(deal, purchase_url=purchase_url)
                if self._comment_on_post
                else ""
            ),
            "comment_on_post": self._comment_on_post,
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
                    if self._comment_on_post and data.get("commentResult"):
                        logger.info(
                            f"Facebook published deal {deal.id} with comment "
                            f"{data['commentResult'].get('commentConfirmation', {}).get('confirmation', 'unknown')}"
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
