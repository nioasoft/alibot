"""Internal redirect-based click tracking for outbound affiliate links."""

from __future__ import annotations

import datetime
import hashlib
import secrets

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from bot.models import AffiliateClickEvent, AffiliateLinkToken, Deal, PublishQueueItem


class LinkTracker:
    def __init__(self, session: Session, base_url: str = "") -> None:
        self._session = session
        self._base_url = base_url.strip().rstrip("/")

    @property
    def is_enabled(self) -> bool:
        return bool(self._base_url)

    def get_or_create_tracked_url(
        self,
        deal: Deal,
        queue_item: PublishQueueItem,
        target_url: str,
    ) -> str:
        if not self.is_enabled or not target_url:
            return target_url

        existing = self._session.execute(
            select(AffiliateLinkToken).where(
                AffiliateLinkToken.queue_item_id == queue_item.id,
            )
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
