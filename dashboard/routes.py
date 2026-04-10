"""Dashboard route handlers."""

from __future__ import annotations

import datetime

from fastapi import FastAPI, Request
from starlette.responses import RedirectResponse
from sqlalchemy import select, func

from bot.models import Deal, PublishQueueItem, DailyStat


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

            recent_rows = session.execute(
                select(Deal, PublishQueueItem.status)
                .outerjoin(PublishQueueItem, Deal.id == PublishQueueItem.deal_id)
                .order_by(Deal.created_at.desc())
                .limit(20)
            ).all()

            return templates.TemplateResponse(
                request, "index.html", {
                    "stats": stats,
                    "queue_count": queue_count,
                    "recent_deals": recent_rows,
                    "auto_refresh": config.dashboard.auto_refresh_seconds,
                },
            )
        finally:
            session.close()

    @app.get("/deals")
    async def deals_list(request: Request, status: str = "", category: str = ""):
        session = app.state.session_factory()
        templates = app.state.templates

        try:
            query = (
                select(Deal, PublishQueueItem.status)
                .outerjoin(PublishQueueItem, Deal.id == PublishQueueItem.deal_id)
            )
            if status:
                query = query.where(PublishQueueItem.status == status)
            if category:
                query = query.where(Deal.category == category)

            query = query.order_by(Deal.created_at.desc()).limit(100)
            deals = session.execute(query).all()

            categories = [
                r[0] for r in session.execute(
                    select(Deal.category).distinct()
                ).all()
            ]

            return templates.TemplateResponse(
                request, "deals.html", {
                    "deals": deals,
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

        try:
            deal = session.get(Deal, deal_id)
            if deal is None:
                return templates.TemplateResponse(
                    request, "index.html", {
                        "stats": DailyStat(
                            date=datetime.date.today(),
                            deals_seen=0, deals_processed=0, deals_published=0,
                            deals_skipped_dup=0, deals_skipped_error=0, api_calls=0,
                        ),
                        "queue_count": 0,
                        "recent_deals": [],
                    }, status_code=404,
                )

            queue_item = session.execute(
                select(PublishQueueItem)
                .where(PublishQueueItem.deal_id == deal_id)
                .limit(1)
            ).scalar_one_or_none()

            return templates.TemplateResponse(
                request, "deal_detail.html", {
                    "deal": deal,
                    "queue_item": queue_item,
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
                request, "queue.html", {"items": items},
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
            request, "settings.html", {"config": config},
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
            request, "logs.html", {"log_content": log_content},
        )
