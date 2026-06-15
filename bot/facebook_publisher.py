"""Facebook publisher adapter backed by the local Playwright service."""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Awaitable, Callable, Optional

import httpx
from loguru import logger
from sqlalchemy.orm import Session

from bot.http_client import new_async_client
from bot.models import Deal, FacebookGroupState

_STRUCTURED_PREFIXES = (
    "💰",
    "🚚",
    "🎟️",
    "🛒",
    "🌐",
)

_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)

# identityMode values that mean the post genuinely went out from the personal
# profile (worth alerting). "page-unverified-session" is a known false-negative
# — it fires when the page name matches the group name — so it is NOT alerted.
_PERSONAL_IDENTITY_MODE = "profile-default"

NotifyFunc = Callable[[str], Awaitable[None]]


class FacebookPublisher:
    def __init__(
        self,
        service_url: str = "http://localhost:3002",
        site_url: str = "",
        comment_on_post: bool = True,
        session: Optional[Session] = None,
        notify_func: Optional[NotifyFunc] = None,
    ):
        self._service_url = service_url
        self._site_url = site_url.rstrip("/")
        self._comment_on_post = comment_on_post
        self._session = session
        self._notify = notify_func
        self._enabled = bool(service_url and site_url)
        self._client: Optional[httpx.AsyncClient] = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = new_async_client(timeout=90.0)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    async def check_health(self) -> bool:
        if not self._enabled:
            return False

        try:
            resp = await self._http().get(f"{self._service_url}/health", timeout=5.0)
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

    def _build_primary_text(self, deal: Deal, comment_on_post: bool) -> str:
        # Compact body: 1-2 description lines + a normalized price/shipping line,
        # so every Facebook post reads consistently (clean ₪ price, no duplicate
        # emoji price lines). Falls back to the raw rewrite if compacting is empty.
        base = self._build_compact_primary_text(deal) or deal.rewritten_text
        if comment_on_post:
            return f"{base}\n🛒 לרכישה: בתגובה הראשונה"
        return base

    def _build_link_text(
        self, deal: Deal, comment_on_post: bool, purchase_url: str | None = None
    ) -> str:
        extra_lines: list[str] = []
        landing_url = self._landing_url_for(deal)
        if landing_url and not comment_on_post:
            extra_lines.append(f"🌐 להצטרפות לקבוצות לפי תחומי עניין: {landing_url}")

        purchase_url = purchase_url or deal.affiliate_link or deal.product_link
        if purchase_url:
            if comment_on_post:
                extra_lines.append(f"🛒 קישור לרכישה: {purchase_url}")
            else:
                extra_lines.append(f"🛒 לרכישה: {purchase_url}")

        if not extra_lines:
            return ""
        return "\n".join(extra_lines)

    def _build_append_text(
        self, deal: Deal, comment_on_post: bool, purchase_url: str | None = None
    ) -> str:
        link_text = self._build_link_text(
            deal, comment_on_post=comment_on_post, purchase_url=purchase_url
        )
        if not link_text:
            return ""
        return "\n\n" + link_text

    def _image_path_for(self, deal: Deal) -> str:
        if not deal.image_path:
            return ""
        return str(Path(deal.image_path).resolve())

    def _group_state(self, group_url: str) -> FacebookGroupState | None:
        if self._session is None:
            return None
        return self._session.get(FacebookGroupState, group_url)

    def _effective_comment_on_post(self, group_url: str) -> bool:
        """Approval-required groups must carry the link in the post body, so the
        first comment is disabled for them regardless of the global default."""
        state = self._group_state(group_url)
        if state is not None and state.approval_required:
            return False
        return self._comment_on_post

    async def _record_outcome(
        self, group_url: str, *, pending: bool, identity_mode: str | None
    ) -> None:
        """Persist learned per-group state and alert the admin on regressions."""
        if self._session is None:
            return

        state = self._session.get(FacebookGroupState, group_url)
        if state is None:
            state = FacebookGroupState(group_url=group_url)
            self._session.add(state)

        previous_identity_mode = state.last_identity_mode
        newly_requires_approval = pending and not state.approval_required
        fell_back_to_personal = (
            identity_mode == _PERSONAL_IDENTITY_MODE
            and previous_identity_mode != _PERSONAL_IDENTITY_MODE
        )

        if pending:
            state.approval_required = True
        state.last_identity_mode = identity_mode
        state.posts_count = (state.posts_count or 0) + 1
        state.updated_at = datetime.datetime.now(datetime.UTC)
        self._session.commit()

        if newly_requires_approval:
            await self._send_admin(
                "🟡 פוסט בקבוצת פייסבוק ממתין לאישור מנהל:\n"
                f"{group_url}\n"
                "מעכשיו הלינק ייכנס לגוף הפוסט (לא בתגובה) בקבוצה הזו."
            )
        if fell_back_to_personal:
            await self._send_admin(
                "⚠️ פוסט בפייסבוק פורסם מהפרופיל האישי ולא מהעמוד:\n"
                f"{group_url}\n"
                "כדאי לרענן את זהות העמוד במק מיני (refresh-auth)."
            )

    async def _send_admin(self, text: str) -> None:
        if self._notify is None:
            return
        try:
            await self._notify(text)
        except Exception as e:  # never let an alert failure mask publishing
            logger.error(f"Facebook admin notification failed: {e}")

    async def send_deal(self, deal: Deal, group_url: str, purchase_url: str | None = None) -> bool:
        if not self._enabled:
            logger.warning("Facebook publisher is disabled")
            return False

        comment_on_post = self._effective_comment_on_post(group_url)
        payload = {
            "group_url": group_url,
            "text": self._build_primary_text(deal, comment_on_post),
            "image_path": self._image_path_for(deal),
            "append_text": (
                ""
                if comment_on_post
                else self._build_append_text(
                    deal, comment_on_post=comment_on_post, purchase_url=purchase_url
                )
            ),
            "comment_text": (
                self._build_link_text(
                    deal, comment_on_post=comment_on_post, purchase_url=purchase_url
                )
                if comment_on_post
                else ""
            ),
            "comment_on_post": comment_on_post,
            "dry_run": False,
        }

        try:
            resp = await self._http().post(f"{self._service_url}/publish", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("imageUpload") == "failed":
                    logger.warning(
                        f"Facebook published deal {deal.id} without uploaded image; "
                        f"falling back to link-only post"
                    )
                if comment_on_post and data.get("commentResult"):
                    logger.info(
                        f"Facebook published deal {deal.id} with comment "
                        f"{data['commentResult'].get('commentConfirmation', {}).get('confirmation', 'unknown')}"
                    )

                ok = bool(data.get("ok"))
                if ok:
                    await self._record_outcome(
                        group_url,
                        pending=bool(data.get("pending")),
                        identity_mode=data.get("identityMode"),
                    )
                return ok

            logger.error(f"Facebook send failed: {resp.status_code} {resp.text}")
            return False
        except httpx.ConnectError:
            logger.warning("Facebook service not running")
            return False
        except Exception as e:
            logger.error(f"Facebook send error: {e}")
            return False
