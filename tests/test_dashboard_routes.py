import datetime

from bot.models import PublishQueueItem
from dashboard.routes import _status_summary


def _queue_item(status: str) -> PublishQueueItem:
    now = datetime.datetime.now(datetime.UTC)
    return PublishQueueItem(
        deal_id=1,
        target_group="legacy",
        destination_key=f"{status}-dest",
        platform="telegram",
        target_ref="@target",
        status=status,
        priority=0,
        scheduled_after=now,
        published_at=None,
        message_id=None,
        error_message=None,
    )


def test_status_summary_compacts_multiple_queue_items() -> None:
    summary = _status_summary(
        [
            _queue_item("published"),
            _queue_item("queued"),
            _queue_item("queued"),
        ]
    )

    assert summary == {
        "label": "✅ 1 פורסם · ⏳ 2 בתור",
        "class_name": "text-blue-600",
    }


def test_status_summary_handles_empty_queue() -> None:
    assert _status_summary([]) == {
        "label": "—",
        "class_name": "text-gray-400",
    }
