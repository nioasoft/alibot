"""Dashboard route handlers."""

from __future__ import annotations

import datetime

from fastapi import FastAPI, Request
from sqlalchemy import func, select
from starlette.responses import RedirectResponse

from bot.models import DailyStat, Deal, PublishQueueItem


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


def register_routes(app: FastAPI) -> None:
    @app.get("/")
    async def index(request: Request):
        session = app.state.session_factory()
        config = app.state.config
        templates = app.state.templates

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

            return templates.TemplateResponse(
                request,
                "index.html",
                {
                    "stats": stats,
                    "queue_count": queue_count,
                    "recent_deals": recent_deals,
                    "queue_summary": queue_summary,
                    "auto_refresh": config.dashboard.auto_refresh_seconds,
                },
            )
        finally:
            session.close()

    @app.get("/deals")
    async def deals_list(request: Request, category: str = ""):
        session = app.state.session_factory()
        templates = app.state.templates

        try:
            query = select(Deal)
            if category:
                query = query.where(Deal.category == category)

            deals = session.execute(
                query.order_by(Deal.created_at.desc()).limit(100)
            ).scalars().all()

            queue_summary = _queue_summary(session, [deal.id for deal in deals])
            categories = [r[0] for r in session.execute(select(Deal.category).distinct()).all()]

            return templates.TemplateResponse(
                request,
                "deals.html",
                {
                    "deals": deals,
                    "queue_summary": queue_summary,
                    "categories": categories,
                    "filter_category": category,
                },
            )
        finally:
            session.close()

    @app.get("/deals/{deal_id}")
    async def deal_detail(request: Request, deal_id: int):
        session = app.state.session_factory()
        templates = app.state.templates

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

            return templates.TemplateResponse(
                request,
                "deal_detail.html",
                {
                    "deal": deal,
                    "queue_items": queue_items,
                },
            )
        finally:
            session.close()

    @app.get("/queue")
    async def queue_page(request: Request):
        session = app.state.session_factory()
        templates = app.state.templates

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

            return templates.TemplateResponse(
                request,
                "queue.html",
                {"items": items},
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
        return templates.TemplateResponse(
            request,
            "settings.html",
            {"config": config},
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
