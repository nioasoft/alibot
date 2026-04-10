"""Queue-based deal publisher with rate limiting and quiet hours."""

from __future__ import annotations

import datetime
import random
from typing import TYPE_CHECKING, Callable, Awaitable, Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session
from loguru import logger

from bot.models import Deal, PublishQueueItem, DailyStat

if TYPE_CHECKING:
    from bot.whatsapp_publisher import WhatsAppPublisher


class DealPublisher:
    def __init__(
        self,
        send_func: Callable[..., Awaitable[int]],
        session: Session,
        min_delay: int,
        max_delay: int,
        max_posts_per_hour: int,
        quiet_hours_start: int,
        quiet_hours_end: int,
        whatsapp_publisher: Optional["WhatsAppPublisher"] = None,
        channel_link: str = "",
        whatsapp_link: str = "",
    ):
        self._send = send_func
        self._session = session
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._max_posts_per_hour = max_posts_per_hour
        self._quiet_start = quiet_hours_start
        self._quiet_end = quiet_hours_end
        self._whatsapp = whatsapp_publisher
        self._channel_link = channel_link
        self._whatsapp_link = whatsapp_link
        self.paused = False

    def pick_next(self) -> Optional[PublishQueueItem]:
        """Get the oldest queued item ready to publish."""
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
        """Return True if the given time (or current time) falls in quiet hours."""
        if now is None:
            now = datetime.datetime.now()
        hour = now.hour
        if self._quiet_start > self._quiet_end:
            # Wraps around midnight: quiet from quiet_start until quiet_end next day
            return hour >= self._quiet_start or hour < self._quiet_end
        return self._quiet_start <= hour < self._quiet_end

    def is_rate_limited(self, target_group: str) -> bool:
        """Return True if the target group has hit the hourly post limit."""
        one_hour_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
        count = self._session.execute(
            select(func.count())
            .select_from(PublishQueueItem)
            .where(
                PublishQueueItem.target_group == target_group,
                PublishQueueItem.status == "published",
                PublishQueueItem.published_at >= one_hour_ago,
            )
        ).scalar()
        return (count or 0) >= self._max_posts_per_hour

    async def publish_one(self, queue_item: PublishQueueItem, deal: Deal) -> None:
        """Publish a single deal and update its status."""
        queue_item.status = "publishing"
        self._session.flush()

        try:
            message_id = await self._send(
                target_group=queue_item.target_group,
                text=deal.rewritten_text,
                link=deal.affiliate_link or deal.product_link,
                image_path=deal.image_path,
            )

            queue_item.status = "published"
            queue_item.published_at = datetime.datetime.now(datetime.UTC)
            queue_item.message_id = message_id
            self._session.commit()

            self._increment_stat("deals_published")
            logger.info(f"Published deal {deal.id} to {queue_item.target_group}")

            # Also send to WhatsApp if enabled
            if self._whatsapp and self._whatsapp.is_enabled:
                link = deal.affiliate_link or deal.product_link
                wa_text = f"{deal.rewritten_text}\n\n🛒 לרכישה: {link}"
                if self._channel_link or self._whatsapp_link:
                    wa_text += "\n\n📢 הצטרפו אלינו:"
                    if self._channel_link:
                        wa_text += f"\nטלגרם: {self._channel_link}"
                    if self._whatsapp_link:
                        wa_text += f"\nוואטסאפ: {self._whatsapp_link}"
                await self._whatsapp.send_deal(
                    text=wa_text,
                    image_path=deal.image_path,
                )

        except Exception as e:
            queue_item.status = "failed"
            queue_item.error_message = str(e)[:500]
            self._session.commit()
            logger.error(f"Failed to publish deal {deal.id}: {e}")
            raise

    async def check_queue(self) -> None:
        """Called by scheduler: pick next deal and publish if conditions allow."""
        if self.paused:
            return

        if self.is_quiet_hour():
            return

        item = self.pick_next()
        if item is None:
            return

        if self.is_rate_limited(item.target_group):
            logger.debug(f"Rate limited for {item.target_group}, skipping cycle")
            return

        deal = self._session.get(Deal, item.deal_id)
        if deal is None:
            item.status = "failed"
            item.error_message = "Deal not found"
            self._session.commit()
            return

        await self.publish_one(item, deal)

    def get_random_delay(self) -> int:
        """Return a random delay in seconds within configured bounds."""
        return random.randint(self._min_delay, self._max_delay)

    def _increment_stat(self, field: str) -> None:
        """Increment a daily stat counter for today."""
        today = datetime.date.today()
        stat = self._session.query(DailyStat).filter_by(date=today).first()
        if stat is None:
            stat = DailyStat(date=today)
            self._session.add(stat)
        setattr(stat, field, (getattr(stat, field) or 0) + 1)
        self._session.flush()
