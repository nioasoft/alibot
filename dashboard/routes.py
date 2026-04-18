"""Dashboard route handlers."""

from __future__ import annotations

import datetime
from collections import Counter
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from sqlalchemy import func, select
from starlette.responses import RedirectResponse

from bot.config import DestinationConfig
from bot.link_tracking import LinkTracker
from bot.models import DailyStat, Deal, PublishQueueItem

_PLATFORM_META = {
    "telegram": {"label": "טלגרם", "class_name": "bg-sky-100 text-sky-800"},
    "whatsapp": {"label": "ווטסאפ", "class_name": "bg-emerald-100 text-emerald-800"},
    "facebook": {"label": "פייסבוק", "class_name": "bg-indigo-100 text-indigo-800"},
    "web": {"label": "אתר", "class_name": "bg-amber-100 text-amber-800"},
}

_STATUS_META = {
    "queued": {"label": "בתור", "class_name": "bg-blue-100 text-blue-800"},
    "publishing": {"label": "נשלח עכשיו", "class_name": "bg-violet-100 text-violet-800"},
    "published": {"label": "פורסם", "class_name": "bg-emerald-100 text-emerald-800"},
    "failed": {"label": "נכשל", "class_name": "bg-rose-100 text-rose-800"},
}

_QUEUE_LANE_META = {
    "main": {"label": "ראשי", "class_name": "bg-slate-900 text-white"},
    "category": {"label": "קטגוריה", "class_name": "bg-slate-200 text-slate-800"},
}

_DESTINATION_NAME_OVERRIDES = {
    "tg_main": "ערוץ טלגרם ראשי",
    "wa_general": "ווטסאפ כללי",
    "wa_main": "ווטסאפ ראשי",
    "wa_tech": "ווטסאפ טכנולוגיה",
    "wa_home": "ווטסאפ לבית",
    "wa_style": "ווטסאפ סטייל וספורט",
    "wa_beauty": "ווטסאפ ביוטי",
    "fb_main": "קבוצת פייסבוק ראשית",
    "fb_beer_sheva_together": "קבוצת פייסבוק באר שבע ביחד",
    "fb_netivot_together": "קבוצת פייסבוק נתיבות ביחד",
    "fb_healthy_lifestyle": "קבוצת פייסבוק אורח חיים בריא",
    "fb_beer_sheva_businesses": "קבוצת פייסבוק עסקים בבאר שבע והסביבה",
    "fb_merhavim_updates": "קבוצת פייסבוק מרחבים - ואתם בעניינים",
    "fb_group_534710937121700": "קבוצת פייסבוק 534710937121700",
    "fb_group_441237999359320": "קבוצת פייסבוק 441237999359320",
    "fb_group_434701246897267": "קבוצת פייסבוק 434701246897267",
    "web_feed": "פיד האתר",
}

_DESTINATION_SEGMENT_LABELS = {
    "main": "ראשי",
    "general": "כללי",
    "tech": "טכנולוגיה",
    "home": "בית",
    "style": "סטייל",
    "beauty": "ביוטי",
    "feed": "פיד",
}


def _platform_meta(platform: str) -> dict[str, str]:
    return _PLATFORM_META.get(
        platform,
        {"label": platform or "לא ידוע", "class_name": "bg-slate-100 text-slate-700"},
    )


def _status_meta(status: str) -> dict[str, str]:
    return _STATUS_META.get(
        status,
        {"label": status or "לא ידוע", "class_name": "bg-slate-100 text-slate-700"},
    )


def _humanize_destination_key(destination_key: str, platform: str) -> str:
    if destination_key in _DESTINATION_NAME_OVERRIDES:
        return _DESTINATION_NAME_OVERRIDES[destination_key]

    parts = destination_key.split("_")
    suffix = parts[1:] if len(parts) > 1 else parts
    readable_suffix = " ".join(
        _DESTINATION_SEGMENT_LABELS.get(part, part.replace("-", " ").title())
        for part in suffix
    ).strip()
    platform_label = _platform_meta(platform)["label"]
    return f"{platform_label} {readable_suffix}".strip()


def _format_target_ref(platform: str, target_ref: str) -> str:
    if not target_ref:
        return "—"

    if platform == "facebook":
        parsed = urlparse(target_ref)
        if parsed.netloc and parsed.path:
            return f"{parsed.netloc}{parsed.path}".rstrip("/")
        return target_ref

    if platform == "whatsapp":
        group_id = target_ref.split("@", 1)[0]
        if len(group_id) > 18:
            group_id = f"{group_id[:8]}…{group_id[-6:]}"
        return f"ID {group_id}"

    return target_ref


def _build_queue_item_view(
    item: PublishQueueItem,
    destinations: dict[str, DestinationConfig],
) -> dict[str, object]:
    platform = item.platform or ""
    destination = destinations.get(item.destination_key)
    platform_info = _platform_meta(platform)
    status_info = _status_meta(item.status)
    queue_lane = "main" if destination and "*" in destination.categories else "category"
    queue_lane_info = _QUEUE_LANE_META[queue_lane]

    return {
        "id": item.id,
        "destination_key": item.destination_key,
        "destination_name": _humanize_destination_key(item.destination_key, platform),
        "platform": platform,
        "platform_label": platform_info["label"],
        "platform_class": platform_info["class_name"],
        "target_ref": item.target_ref,
        "target_display": _format_target_ref(platform, item.target_ref),
        "status": item.status,
        "status_label": status_info["label"],
        "status_class": status_info["class_name"],
        "queue_lane": queue_lane,
        "queue_lane_label": queue_lane_info["label"],
        "queue_lane_class": queue_lane_info["class_name"],
        "priority": item.priority,
        "scheduled_after": item.scheduled_after,
        "published_at": item.published_at,
        "error_message": item.error_message,
        "categories": destination.categories if destination else [],
    }


def _queue_details_map(
    queue_summary: dict[int, list[PublishQueueItem]],
    destinations: dict[str, DestinationConfig],
) -> dict[int, list[dict[str, object]]]:
    return {
        deal_id: [_build_queue_item_view(item, destinations) for item in items]
        for deal_id, items in queue_summary.items()
    }


def _recent_publish_rows(
    session,
    destinations: dict[str, DestinationConfig],
    limit: int = 10,
) -> list[dict[str, object]]:
    rows = session.execute(
        select(PublishQueueItem, Deal)
        .join(Deal, PublishQueueItem.deal_id == Deal.id)
        .where(PublishQueueItem.status == "published")
        .order_by(PublishQueueItem.published_at.desc(), PublishQueueItem.id.desc())
        .limit(limit)
    ).all()

    return [
        {
            "deal": deal,
            "queue_item": _build_queue_item_view(queue_item, destinations),
        }
        for queue_item, deal in rows
    ]


def _queue_summary(session, deal_ids: list[int]) -> dict[int, list[PublishQueueItem]]:
    if not deal_ids:
        return {}

    rows = session.execute(
        select(PublishQueueItem)
        .where(PublishQueueItem.deal_id.in_(deal_ids))
        .order_by(PublishQueueItem.id.asc())
    ).scalars().all()

    summary: dict[int, list[PublishQueueItem]] = {}
    for row in rows:
        summary.setdefault(row.deal_id, []).append(row)
    return summary


def _status_summary(queue_items: list[PublishQueueItem]) -> dict[str, str]:
    if not queue_items:
        return {"label": "—", "class_name": "text-gray-400"}

    counts = Counter(item.status for item in queue_items)
    parts: list[str] = []

    if counts["published"]:
        parts.append(f"✅ {counts['published']} פורסם")
    if counts["queued"]:
        parts.append(f"⏳ {counts['queued']} בתור")
    if counts["failed"]:
        parts.append(f"⚠️ {counts['failed']} נכשל")

    for status, count in sorted(counts.items()):
        if status in {"published", "queued", "failed"}:
            continue
        parts.append(f"{status}: {count}")

    if counts["queued"]:
        class_name = "text-blue-600"
    elif counts["published"] and not counts["failed"]:
        class_name = "text-green-600"
    elif counts["failed"]:
        class_name = "text-red-600"
    else:
        class_name = "text-gray-500"

    return {"label": " · ".join(parts), "class_name": class_name}


def _status_summary_map(
    queue_summary: dict[int, list[PublishQueueItem]],
) -> dict[int, dict[str, str]]:
    return {
        deal_id: _status_summary(items)
        for deal_id, items in queue_summary.items()
    }


def register_routes(app: FastAPI) -> None:
    @app.get("/go/{token}")
    async def tracked_redirect(request: Request, token: str):
        session = app.state.session_factory()

        try:
            tracking_config = getattr(app.state.config, "tracking", None)
            tracker = LinkTracker(
                session=session,
                base_url=getattr(tracking_config, "base_url", ""),
            )
            token_record = tracker.get_token_record(token)
            if token_record is None:
                raise HTTPException(status_code=404, detail="Unknown tracking token")

            tracker.record_click(token_record, request)
            return RedirectResponse(url=token_record.target_url, status_code=302)
        finally:
            session.close()

    @app.get("/")
    async def index(request: Request):
        session = app.state.session_factory()
        config = app.state.config
        templates = app.state.templates
        destinations = config.publishing.destinations or {}

        try:
            today = datetime.date.today()
            stats = session.query(DailyStat).filter_by(date=today).first()
            if stats is None:
                stats = DailyStat(
                    date=today,
                    deals_seen=0,
                    deals_processed=0,
                    deals_published=0,
                    deals_skipped_dup=0,
                    deals_skipped_error=0,
                    api_calls=0,
                )

            queue_count = session.execute(
                select(func.count())
                .select_from(PublishQueueItem)
                .where(PublishQueueItem.status == "queued")
            ).scalar() or 0

            recent_deals = session.execute(
                select(Deal).order_by(Deal.created_at.desc()).limit(20)
            ).scalars().all()
            queue_summary = _queue_summary(session, [deal.id for deal in recent_deals])
            status_summary = _status_summary_map(queue_summary)
            queue_details = _queue_details_map(queue_summary, destinations)
            recent_publishes = _recent_publish_rows(session, destinations)

            return templates.TemplateResponse(
                request,
                "index.html",
                {
                    "stats": stats,
                    "queue_count": queue_count,
                    "recent_deals": recent_deals,
                    "queue_summary": queue_summary,
                    "status_summary": status_summary,
                    "queue_details": queue_details,
                    "recent_publishes": recent_publishes,
                    "auto_refresh": config.dashboard.auto_refresh_seconds,
                },
            )
        finally:
            session.close()

    @app.get("/deals")
    async def deals_list(request: Request, status: str = "", category: str = ""):
        session = app.state.session_factory()
        templates = app.state.templates
        destinations = app.state.config.publishing.destinations or {}

        try:
            query = select(Deal)
            if status:
                query = query.where(
                    select(PublishQueueItem.id)
                    .where(
                        PublishQueueItem.deal_id == Deal.id,
                        PublishQueueItem.status == status,
                    )
                    .exists()
                )
            if category:
                query = query.where(Deal.category == category)

            deals = session.execute(
                query.order_by(Deal.created_at.desc()).limit(100)
            ).scalars().all()

            queue_summary = _queue_summary(session, [deal.id for deal in deals])
            status_summary = _status_summary_map(queue_summary)
            queue_details = _queue_details_map(queue_summary, destinations)
            categories = [r[0] for r in session.execute(select(Deal.category).distinct()).all()]

            return templates.TemplateResponse(
                request,
                "deals.html",
                {
                    "deals": deals,
                    "queue_summary": queue_summary,
                    "status_summary": status_summary,
                    "queue_details": queue_details,
                    "categories": categories,
                    "filter_status": status,
                    "filter_category": category,
                },
            )
        finally:
            session.close()

    @app.get("/deals/{deal_id}")
    async def deal_detail(request: Request, deal_id: int):
        session = app.state.session_factory()
        templates = app.state.templates
        destinations = app.state.config.publishing.destinations or {}

        try:
            deal = session.get(Deal, deal_id)
            if deal is None:
                return templates.TemplateResponse(
                    request,
                    "index.html",
                    {
                        "stats": DailyStat(
                            date=datetime.date.today(),
                            deals_seen=0,
                            deals_processed=0,
                            deals_published=0,
                            deals_skipped_dup=0,
                            deals_skipped_error=0,
                            api_calls=0,
                        ),
                        "queue_count": 0,
                        "recent_deals": [],
                        "queue_summary": {},
                    },
                    status_code=404,
                )

            queue_items = session.execute(
                select(PublishQueueItem)
                .where(PublishQueueItem.deal_id == deal_id)
                .order_by(PublishQueueItem.id.asc())
            ).scalars().all()
            queue_details = [_build_queue_item_view(item, destinations) for item in queue_items]

            return templates.TemplateResponse(
                request,
                "deal_detail.html",
                {
                    "deal": deal,
                    "queue_items": queue_details,
                },
            )
        finally:
            session.close()

    @app.get("/queue")
    async def queue_page(request: Request):
        session = app.state.session_factory()
        templates = app.state.templates
        destinations = app.state.config.publishing.destinations or {}

        try:
            items = session.execute(
                select(PublishQueueItem, Deal)
                .join(Deal, PublishQueueItem.deal_id == Deal.id)
                .where(PublishQueueItem.status == "queued")
                .order_by(
                    PublishQueueItem.priority.desc(),
                    PublishQueueItem.scheduled_after.asc(),
                )
            ).all()
            queue_rows = [
                {
                    "deal": deal,
                    "queue_item": _build_queue_item_view(queue_item, destinations),
                }
                for queue_item, deal in items
            ]

            return templates.TemplateResponse(
                request,
                "queue.html",
                {"items": queue_rows},
            )
        finally:
            session.close()

    @app.post("/queue/{item_id}/skip")
    async def queue_skip(item_id: int):
        session = app.state.session_factory()
        try:
            item = session.get(PublishQueueItem, item_id)
            if item and item.status == "queued":
                item.status = "failed"
                item.error_message = "Skipped from dashboard"
                session.commit()
        finally:
            session.close()
        return RedirectResponse(url="/queue", status_code=303)

    @app.post("/queue/{item_id}/promote")
    async def queue_promote(item_id: int):
        session = app.state.session_factory()
        try:
            item = session.get(PublishQueueItem, item_id)
            if item and item.status == "queued":
                item.priority += 10
                session.commit()
        finally:
            session.close()
        return RedirectResponse(url="/queue", status_code=303)

    @app.get("/settings")
    async def settings_page(request: Request):
        templates = app.state.templates
        config = app.state.config
        destinations = config.publishing.destinations or {}
        destination_rows = [
            {
                "key": key,
                "name": _humanize_destination_key(key, destination.platform),
                "platform_label": _platform_meta(destination.platform)["label"],
                "platform_class": _platform_meta(destination.platform)["class_name"],
                "target_display": _format_target_ref(destination.platform, destination.target),
                "target_ref": destination.target,
                "categories": destination.categories,
                "enabled": destination.enabled,
            }
            for key, destination in destinations.items()
        ]
        return templates.TemplateResponse(
            request,
            "settings.html",
            {"config": config, "destination_rows": destination_rows},
        )

    @app.get("/logs")
    async def logs_page(request: Request):
        templates = app.state.templates
        log_path = "data/bot.log"
        log_content = ""
        try:
            with open(log_path) as f:
                lines = f.readlines()
                log_content = "".join(lines[-100:])
        except FileNotFoundError:
            log_content = "No log file found yet."
        return templates.TemplateResponse(
            request,
            "logs.html",
            {"log_content": log_content},
        )
