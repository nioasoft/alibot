"""Telegram admin commands for bot control."""

from __future__ import annotations

import datetime

from sqlalchemy import select, func
from sqlalchemy.orm import Session
from loguru import logger

from bot.models import Deal, PublishQueueItem, DailyStat


class AdminCommands:
    def __init__(
        self,
        session: Session,
        admin_user_id: int,
        publisher,
    ):
        self._session = session
        self._admin_user_id = admin_user_id
        self._publisher = publisher

    def is_admin(self, user_id: int) -> bool:
        return user_id == self._admin_user_id

    async def handle_command(self, user_id: int, text: str) -> str | None:
        """Parse and execute admin command. Returns response text or None."""
        if not self.is_admin(user_id):
            return None

        text = text.strip()
        if text == "/stats":
            return self._cmd_stats()
        elif text == "/pause":
            return self._cmd_pause()
        elif text == "/resume":
            return self._cmd_resume()
        elif text == "/queue":
            return self._cmd_queue()
        elif text.startswith("/skip"):
            return self._cmd_skip(text)
        elif text == "/last":
            return self._cmd_last()

        return None

    def _cmd_stats(self) -> str:
        today = datetime.date.today()
        stat = self._session.query(DailyStat).filter_by(date=today).first()
        if stat is None:
            return "📊 אין סטטיסטיקות להיום."
        return (
            f"📊 סטטיסטיקות — {today.isoformat()}\n\n"
            f"👀 נראו: {stat.deals_seen}\n"
            f"✅ עובדו: {stat.deals_processed}\n"
            f"📤 פורסמו: {stat.deals_published}\n"
            f"🔁 כפילויות: {stat.deals_skipped_dup}\n"
            f"❌ שגיאות: {stat.deals_skipped_error}"
        )

    def _cmd_pause(self) -> str:
        self._publisher.paused = True
        logger.info("Publishing paused by admin")
        return "⏸ פרסום הופסק. העיבוד ממשיך."

    def _cmd_resume(self) -> str:
        self._publisher.paused = False
        logger.info("Publishing resumed by admin")
        return "▶️ פרסום חודש."

    def _cmd_queue(self) -> str:
        count = self._session.execute(
            select(func.count())
            .select_from(PublishQueueItem)
            .where(PublishQueueItem.status == "queued")
        ).scalar()
        return f"📋 {count} דילים בתור לפרסום."

    def _cmd_skip(self, text: str) -> str:
        parts = text.split()
        if len(parts) < 2:
            return "Usage: /skip <deal_id>"
        try:
            deal_id = int(parts[1])
        except ValueError:
            return "Usage: /skip <deal_id> (מספר)"

        item = self._session.execute(
            select(PublishQueueItem).where(
                PublishQueueItem.deal_id == deal_id,
                PublishQueueItem.status == "queued",
            )
        ).scalar_one_or_none()

        if item is None:
            return f"לא נמצא דיל {deal_id} בתור."

        item.status = "failed"
        item.error_message = "Skipped by admin"
        self._session.commit()
        return f"⏭ דיל {deal_id} דולג."

    def _cmd_last(self) -> str:
        items = self._session.execute(
            select(PublishQueueItem, Deal)
            .join(Deal, PublishQueueItem.deal_id == Deal.id)
            .where(PublishQueueItem.status == "published")
            .order_by(PublishQueueItem.published_at.desc())
            .limit(5)
        ).all()

        if not items:
            return "אין פרסומים אחרונים."

        lines = ["📤 5 אחרונים:\n"]
        for qi, deal in items:
            time_str = qi.published_at.strftime("%H:%M") if qi.published_at else "?"
            lines.append(f"• [{time_str}] {deal.product_name[:40]} — ₪{deal.price}")

        return "\n".join(lines)
