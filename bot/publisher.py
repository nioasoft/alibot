"""Queue-based multi-platform deal publisher with rate limiting and quiet hours."""

from __future__ import annotations

import datetime
import random
from typing import Optional

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bot.models import DailyStat, Deal, PublishQueueItem


class DealPublisher:
    def __init__(
        self,
        session: Session,
        min_delay: int,
        max_delay: int,
        max_posts_per_hour: int,
        quiet_hours_start: int,
        quiet_hours_end: int,
        telegram_publisher=None,
        whatsapp_publisher=None,
        web_publisher=None,
        channel_link: str = "",
        whatsapp_link: str = "",
    ):
        self._session = session
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._max_posts_per_hour = max_posts_per_hour
        self._quiet_start = quiet_hours_start
        self._quiet_end = quiet_hours_end
        self._telegram = telegram_publisher
        self._whatsapp = whatsapp_publisher
        self._web = web_publisher
        self._channel_link = channel_link
        self._whatsapp_link = whatsapp_link
        self.paused = False

    def pick_next(self) -> Optional[PublishQueueItem]:
        now = datetime.datetime.now(datetime.UTC)
        return self._session.execute(
            select(PublishQueueItem)
            .where(
                PublishQueueItem.status == "queued",
                PublishQueueItem.scheduled_after <= now,
            )
            .order_by(
                PublishQueueItem.priority.desc(),
                PublishQueueItem.scheduled_after.asc(),
            )
            .limit(1)
        ).scalar_one_or_none()

    def is_quiet_hour(self, now: Optional[datetime.datetime] = None) -> bool:
        if now is None:
            now = datetime.datetime.now()
        hour = now.hour
        if self._quiet_start > self._quiet_end:
            return hour >= self._quiet_start or hour < self._quiet_end
        return self._quiet_start <= hour < self._quiet_end

    def is_rate_limited(self, target_ref: str) -> bool:
        one_hour_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
        count = self._session.execute(
            select(func.count())
            .select_from(PublishQueueItem)
            .where(
                PublishQueueItem.target_ref == target_ref,
                PublishQueueItem.status == "published",
                PublishQueueItem.published_at >= one_hour_ago,
            )
        ).scalar()
        return (count or 0) >= self._max_posts_per_hour

    def _build_social_text(self, deal: Deal) -> str:
        link = deal.affiliate_link or deal.product_link
        text = f"{deal.rewritten_text}\n\n🛒 לרכישה: {link}"
        if self._channel_link or self._whatsapp_link:
            text += "\n\n📢 הצטרפו אלינו:"
            if self._channel_link:
                text += f"\nטלגרם: {self._channel_link}"
            if self._whatsapp_link:
                text += f"\nוואטסאפ: {self._whatsapp_link}"
        return text

    async def publish_one(self, queue_item: PublishQueueItem, deal: Deal) -> None:
        queue_item.status = "publishing"
        self._session.flush()

        try:
            message_id = None
            link = deal.affiliate_link or deal.product_link

            if queue_item.platform == "telegram":
                if self._telegram is None:
                    raise RuntimeError("Telegram publisher is not configured")
                message_id = await self._telegram.send_deal(
                    target_ref=queue_item.target_ref,
                    text=deal.rewritten_text,
                    link=link,
                    image_path=deal.image_path,
                )
            elif queue_item.platform == "whatsapp":
                if self._whatsapp is None:
                    raise RuntimeError("WhatsApp publisher is not configured")
                ok = await self._whatsapp.send_deal(
                    text=self._build_social_text(deal),
                    image_path=deal.image_path,
                    group_jid=queue_item.target_ref,
                )
                if not ok:
                    raise RuntimeError("WhatsApp send failed")
            elif queue_item.platform == "web":
                if self._web is None:
                    raise RuntimeError("Web publisher is not configured")
                ok = await self._web.send_deal(queue_item.target_ref, deal)
                if not ok:
                    raise RuntimeError("Web publish failed")
            else:
                raise RuntimeError(f"Unsupported platform '{queue_item.platform}'")

            queue_item.status = "published"
            queue_item.published_at = datetime.datetime.now(datetime.UTC)
            queue_item.message_id = message_id
            self._session.commit()

            self._increment_stat("deals_published")
            logger.info(
                f"Published deal {deal.id} to {queue_item.platform}:{queue_item.target_ref}"
            )
        except Exception as e:
            queue_item.status = "failed"
            queue_item.error_message = str(e)[:500]
            self._session.commit()
            logger.error(f"Failed to publish deal {deal.id}: {e}")
            raise

    async def check_queue(self) -> None:
        if self.paused or self.is_quiet_hour():
            return

        item = self.pick_next()
        if item is None:
            return

        if self.is_rate_limited(item.target_ref):
            logger.debug(f"Rate limited for {item.target_ref}, skipping cycle")
            return

        deal = self._session.get(Deal, item.deal_id)
        if deal is None:
            item.status = "failed"
            item.error_message = "Deal not found"
            self._session.commit()
            return

        await self.publish_one(item, deal)

    def get_random_delay(self) -> int:
        return random.randint(self._min_delay, self._max_delay)

    def _increment_stat(self, field: str) -> None:
        today = datetime.date.today()
        stat = self._session.query(DailyStat).filter_by(date=today).first()
        if stat is None:
            stat = DailyStat(date=today)
            self._session.add(stat)
        setattr(stat, field, (getattr(stat, field) or 0) + 1)
        self._session.flush()
