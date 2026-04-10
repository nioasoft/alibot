"""Send error alerts and daily summaries to admin via Telegram."""

from __future__ import annotations

import datetime

from sqlalchemy.orm import Session
from loguru import logger

from bot.models import DailyStat


class Notifier:
    def __init__(self, send_message_func, session: Session):
        self._send = send_message_func
        self._session = session

    async def notify_error(self, message: str) -> None:
        """Send critical error alert to admin."""
        text = f"⚠️ שגיאה בבוט:\n{message[:1000]}"
        try:
            await self._send(text)
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")

    async def send_daily_summary(self) -> None:
        """Send daily statistics summary to admin."""
        today = datetime.date.today()
        stat = self._session.query(DailyStat).filter_by(date=today).first()

        if stat is None:
            text = "📊 סיכום יומי:\nלא היתה פעילות היום."
        else:
            text = (
                f"📊 סיכום יומי — {today.isoformat()}\n\n"
                f"👀 דילים שנראו: {stat.deals_seen}\n"
                f"✅ עובדו: {stat.deals_processed}\n"
                f"📤 פורסמו: {stat.deals_published}\n"
                f"🔁 כפילויות: {stat.deals_skipped_dup}\n"
                f"❌ שגיאות: {stat.deals_skipped_error}\n"
                f"🔌 קריאות API: {stat.api_calls}"
            )

        try:
            await self._send(text)
            logger.info("Daily summary sent")
        except Exception as e:
            logger.error(f"Failed to send daily summary: {e}")

    async def notify_startup(self) -> None:
        await self._send("🟢 הבוט עלה לאוויר!")

    async def notify_shutdown(self) -> None:
        await self._send("🔴 הבוט נכבה.")
