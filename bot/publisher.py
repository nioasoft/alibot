"""Queue-based multi-platform deal publisher with rate limiting and quiet hours."""

from __future__ import annotations

import datetime
import random
from typing import Optional

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bot.config import DestinationConfig, InviteLinkConfig
from bot.footer_links import FooterLinkBuilder
from bot.link_tracking import LinkTracker
from bot.models import DailyStat, Deal, PublishQueueItem


def _as_utc(dt: datetime.datetime | None) -> datetime.datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.UTC)
    return dt.astimezone(datetime.UTC)


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
        facebook_publisher=None,
        web_publisher=None,
        site_url: str = "",
        tracking_base_url: str = "",
        tracking_api_secret: str = "",
        invite_links: list[InviteLinkConfig] | None = None,
        destinations: dict[str, DestinationConfig] | None = None,
        weekend_reduced_rate_factor: float = 1.0,
        weekend_reduced_start_weekday: int = 4,
        weekend_reduced_start_hour: int = 18,
        weekend_reduced_end_weekday: int = 5,
        weekend_reduced_end_hour: int = 18,
    ):
        self._session = session
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._max_posts_per_hour = max_posts_per_hour
        self._quiet_start = quiet_hours_start
        self._quiet_end = quiet_hours_end
        self._telegram = telegram_publisher
        self._whatsapp = whatsapp_publisher
        self._facebook = facebook_publisher
        self._web = web_publisher
        self._footer_links = FooterLinkBuilder(
            site_url=site_url,
            invite_links=invite_links,
        )
        self._link_tracker = LinkTracker(
            session=session,
            base_url=tracking_base_url,
            api_secret=tracking_api_secret,
        )
        self._destinations = destinations or {}
        self._weekend_reduced_rate_factor = weekend_reduced_rate_factor
        self._weekend_reduced_start_weekday = weekend_reduced_start_weekday
        self._weekend_reduced_start_hour = weekend_reduced_start_hour
        self._weekend_reduced_end_weekday = weekend_reduced_end_weekday
        self._weekend_reduced_end_hour = weekend_reduced_end_hour
        self.paused = False

    def _queue_lane_for_item(self, item: PublishQueueItem) -> str:
        destination = self._destinations.get(item.destination_key)
        if destination and "*" in destination.categories:
            return "main"
        return "category"

    def pick_next(
        self,
        queue_lane: str | None = None,
        excluded_item_ids: set[int] | None = None,
    ) -> Optional[PublishQueueItem]:
        now = datetime.datetime.now(datetime.UTC)
        candidates = self._session.execute(
            select(PublishQueueItem)
            .where(
                PublishQueueItem.status == "queued",
                PublishQueueItem.scheduled_after <= now,
            )
            .order_by(
                PublishQueueItem.priority.desc(),
                PublishQueueItem.scheduled_after.asc(),
            )
        ).scalars().all()

        if queue_lane is not None:
            candidates = [
                item for item in candidates
                if self._queue_lane_for_item(item) == queue_lane
            ]
        if excluded_item_ids:
            candidates = [
                item for item in candidates
                if item.id not in excluded_item_ids
            ]

        if not candidates:
            return None

        target_refs = {item.target_ref for item in candidates}
        last_published_by_target = {
            target_ref: self._session.execute(
                select(func.max(PublishQueueItem.published_at)).where(
                    PublishQueueItem.target_ref == target_ref,
                    PublishQueueItem.status == "published",
                )
            ).scalar_one()
            for target_ref in target_refs
        }

        def ranking(item: PublishQueueItem) -> tuple[int, float, float]:
            last_published = _as_utc(last_published_by_target.get(item.target_ref))
            if last_published is None:
                idle_hours = 999.0
            else:
                idle_hours = (now - last_published).total_seconds() / 3600
            scheduled_after = _as_utc(item.scheduled_after) or now
            age_seconds = (now - scheduled_after).total_seconds()
            return (item.priority, idle_hours, age_seconds)

        return max(candidates, key=ranking)

    def is_quiet_hour(self, now: Optional[datetime.datetime] = None) -> bool:
        if now is None:
            now = datetime.datetime.now()
        hour = now.hour
        if self._quiet_start > self._quiet_end:
            return hour >= self._quiet_start or hour < self._quiet_end
        return self._quiet_start <= hour < self._quiet_end

    def _destination_config_for(self, destination_key: str) -> DestinationConfig | None:
        return self._destinations.get(destination_key)

    def _last_published_at(self, target_ref: str) -> datetime.datetime | None:
        last_published = self._session.execute(
            select(func.max(PublishQueueItem.published_at)).where(
                PublishQueueItem.target_ref == target_ref,
                PublishQueueItem.status == "published",
            )
        ).scalar_one()
        return _as_utc(last_published)

    def _local_timezone(self) -> datetime.tzinfo:
        return datetime.datetime.now().astimezone().tzinfo or datetime.UTC

    def _as_local(self, now: datetime.datetime | None = None) -> datetime.datetime:
        if now is None:
            return datetime.datetime.now().astimezone()
        if now.tzinfo is None:
            return now.replace(tzinfo=self._local_timezone())
        return now.astimezone(self._local_timezone())

    def _week_minutes(self, weekday: int, hour: int, minute: int = 0) -> int:
        return weekday * 24 * 60 + hour * 60 + minute

    def _is_weekend_reduced_window(self, now: datetime.datetime | None = None) -> bool:
        if self._weekend_reduced_rate_factor >= 1.0:
            return False

        local_now = self._as_local(now)
        current_minutes = self._week_minutes(
            local_now.weekday(),
            local_now.hour,
            local_now.minute,
        )
        start_minutes = self._week_minutes(
            self._weekend_reduced_start_weekday,
            self._weekend_reduced_start_hour,
        )
        end_minutes = self._week_minutes(
            self._weekend_reduced_end_weekday,
            self._weekend_reduced_end_hour,
        )

        if start_minutes <= end_minutes:
            return start_minutes <= current_minutes < end_minutes
        return current_minutes >= start_minutes or current_minutes < end_minutes

    def _effective_max_posts_per_hour(
        self,
        destination_key: str | None = None,
        now: datetime.datetime | None = None,
    ) -> int:
        destination = self._destination_config_for(destination_key) if destination_key else None
        if destination and destination.platform == "facebook":
            return self._max_posts_per_hour
        if not self._is_weekend_reduced_window(now):
            return self._max_posts_per_hour
        return max(1, int(self._max_posts_per_hour * self._weekend_reduced_rate_factor))

    def is_rate_limited(
        self,
        target_ref: str,
        destination_key: str | None = None,
        now: datetime.datetime | None = None,
    ) -> bool:
        local_now = self._as_local(now)
        now_utc = local_now.astimezone(datetime.UTC)
        one_hour_ago = now_utc - datetime.timedelta(hours=1)
        count = self._session.execute(
            select(func.count())
            .select_from(PublishQueueItem)
            .where(
                PublishQueueItem.target_ref == target_ref,
                PublishQueueItem.status == "published",
                PublishQueueItem.published_at >= one_hour_ago,
            )
        ).scalar()
        max_posts_per_hour = self._effective_max_posts_per_hour(destination_key, local_now)
        if (count or 0) >= max_posts_per_hour:
            return True

        if not destination_key:
            return False

        destination = self._destination_config_for(destination_key)
        min_interval_minutes = destination.min_publish_interval_minutes if destination else 0
        if min_interval_minutes <= 0:
            return False

        last_published = self._last_published_at(target_ref)
        if last_published is None:
            return False

        min_allowed_at = now_utc - datetime.timedelta(minutes=min_interval_minutes)
        return last_published >= min_allowed_at

    def _build_social_text(self, deal: Deal, purchase_url: str) -> str:
        footer = self._footer_links.build_footer(purchase_url, deal.id)
        return f"{deal.rewritten_text}\n\n{footer}"

    async def _build_purchase_url(self, deal: Deal, queue_item: PublishQueueItem) -> str:
        raw_url = deal.affiliate_link or deal.product_link
        return await self._link_tracker.get_or_create_tracked_url(
            deal=deal,
            queue_item=queue_item,
            target_url=raw_url,
        )

    async def publish_one(self, queue_item: PublishQueueItem, deal: Deal) -> None:
        queue_item.status = "publishing"
        self._session.flush()

        try:
            message_id = None
            link = await self._build_purchase_url(deal, queue_item)

            if queue_item.platform == "telegram":
                if self._telegram is None:
                    raise RuntimeError("Telegram publisher is not configured")
                message_id = await self._telegram.send_deal(
                    target_ref=queue_item.target_ref,
                    text=deal.rewritten_text,
                    link=link,
                    deal_id=deal.id,
                    image_path=deal.image_path,
                )
            elif queue_item.platform == "whatsapp":
                if self._whatsapp is None:
                    raise RuntimeError("WhatsApp publisher is not configured")
                ok = await self._whatsapp.send_deal(
                    text=self._build_social_text(deal, link),
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
            elif queue_item.platform == "facebook":
                if self._facebook is None:
                    raise RuntimeError("Facebook publisher is not configured")
                ok = await self._facebook.send_deal(
                    deal=deal,
                    group_url=queue_item.target_ref,
                    purchase_url=link,
                )
                if not ok:
                    raise RuntimeError("Facebook send failed")
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

        for queue_lane in ("main", "category"):
            skipped_item_ids: set[int] = set()

            while True:
                item = self.pick_next(
                    queue_lane=queue_lane,
                    excluded_item_ids=skipped_item_ids,
                )
                if item is None:
                    break

                if self.is_rate_limited(item.target_ref, item.destination_key):
                    logger.debug(
                        f"Rate limited for {item.destination_key}:{item.target_ref}, skipping candidate"
                    )
                    skipped_item_ids.add(item.id)
                    continue

                deal = self._session.get(Deal, item.deal_id)
                if deal is None:
                    item.status = "failed"
                    item.error_message = "Deal not found"
                    self._session.commit()
                    skipped_item_ids.add(item.id)
                    continue

                await self.publish_one(item, deal)
                break

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
