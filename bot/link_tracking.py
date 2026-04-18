"""Internal redirect-based click tracking for outbound affiliate links."""

from __future__ import annotations

import datetime
import hashlib
import secrets
from typing import Any

import httpx
from fastapi import Request
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.models import AffiliateClickEvent, AffiliateLinkToken, Deal, PublishQueueItem


class LinkTracker:
    def __init__(self, session: Session, base_url: str = "", api_secret: str = "") -> None:
        self._session = session
        self._base_url = base_url.strip().rstrip("/")
        self._api_secret = api_secret.strip()

    @property
    def is_enabled(self) -> bool:
        return bool(self._base_url and self._api_secret)

    async def get_or_create_tracked_url(
        self,
        deal: Deal,
        queue_item: PublishQueueItem,
        target_url: str,
    ) -> str:
        if not self.is_enabled or not target_url:
            return target_url

        return await self._create_remote_tracked_url(deal, queue_item, target_url)

    def get_or_create_local_tracked_url(
        self,
        deal: Deal,
        queue_item: PublishQueueItem,
        target_url: str,
    ) -> str:
        if not self._base_url or not target_url:
            return target_url

        existing = self._session.execute(
            select(AffiliateLinkToken).where(AffiliateLinkToken.queue_item_id == queue_item.id)
        ).scalar_one_or_none()
        if existing is not None:
            return self._build_tracking_url(existing.token)

        token_record = AffiliateLinkToken(
            token=self._generate_unique_token(),
            deal_id=deal.id,
            queue_item_id=queue_item.id,
            destination_key=queue_item.destination_key,
            platform=queue_item.platform,
            source_group=deal.source_group,
            affiliate_account_key=deal.affiliate_account_key,
            tracking_id=None,
            custom_parameters=None,
            target_url=target_url,
            created_at=datetime.datetime.now(datetime.UTC),
        )
        self._session.add(token_record)
        self._session.flush()
        return self._build_tracking_url(token_record.token)

    def get_token_record(self, token: str) -> AffiliateLinkToken | None:
        return self._session.execute(
            select(AffiliateLinkToken).where(AffiliateLinkToken.token == token)
        ).scalar_one_or_none()

    def record_click(self, token_record: AffiliateLinkToken, request: Request) -> AffiliateClickEvent:
        click = AffiliateClickEvent(
            token_id=token_record.id,
            deal_id=token_record.deal_id,
            queue_item_id=token_record.queue_item_id,
            destination_key=token_record.destination_key,
            platform=token_record.platform,
            source_group=token_record.source_group,
            clicked_at=datetime.datetime.now(datetime.UTC),
            ip_hash=self._hash_ip(self._extract_ip(request)),
            user_agent=(request.headers.get("user-agent") or "").strip() or None,
            referer=(request.headers.get("referer") or "").strip() or None,
        )
        self._session.add(click)
        self._session.commit()
        return click

    def _build_tracking_url(self, token: str) -> str:
        return f"{self._base_url}/go/{token}"

    async def _create_remote_tracked_url(
        self,
        deal: Deal,
        queue_item: PublishQueueItem,
        target_url: str,
    ) -> str:
        payload = {
            "idempotencyKey": self._idempotency_key(queue_item),
            "targetUrl": target_url,
            "dealId": deal.id,
            "queueItemId": queue_item.id,
            "platform": queue_item.platform,
            "destinationKey": queue_item.destination_key,
            "sourceGroup": deal.source_group,
            "postVariant": "default",
            "metadata": self._metadata_for(deal, queue_item),
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self._base_url}/api/tracking-links",
                    headers={
                        "Content-Type": "application/json",
                        "x-tracking-secret": self._api_secret,
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(f"Tracking link creation failed for queue item {queue_item.id}: {exc}")
            return target_url

        tracked_url = str(response.json().get("trackedUrl", "")).strip()
        if not tracked_url:
            logger.warning(
                f"Tracking API returned no trackedUrl for queue item {queue_item.id}; using raw URL"
            )
            return target_url
        return tracked_url

    @staticmethod
    def _idempotency_key(queue_item: PublishQueueItem) -> str:
        return (
            f"queue:{queue_item.id}:"
            f"{queue_item.platform}:"
            f"{queue_item.destination_key}:"
            f"{queue_item.target_ref}"
        )[:200]

    @staticmethod
    def _metadata_for(deal: Deal, queue_item: PublishQueueItem) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "category": deal.category,
            "ali_category_raw": deal.ali_category_raw,
            "category_source": deal.category_source,
            "affiliate_account_key": deal.affiliate_account_key,
            "product_id": deal.product_id,
            "product_name": deal.product_name,
            "target_group": queue_item.target_group,
        }
        return {key: value for key, value in metadata.items() if value not in (None, "")}

    def _generate_unique_token(self) -> str:
        while True:
            token = secrets.token_urlsafe(6)
            exists = self._session.execute(
                select(AffiliateLinkToken.id).where(AffiliateLinkToken.token == token)
            ).scalar_one_or_none()
            if exists is None:
                return token

    @staticmethod
    def _extract_ip(request: Request) -> str:
        forwarded_for = (request.headers.get("x-forwarded-for") or "").strip()
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return ""

    @staticmethod
    def _hash_ip(ip_address: str) -> str | None:
        if not ip_address:
            return None
        return hashlib.sha256(ip_address.encode("utf-8")).hexdigest()
