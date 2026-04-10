"""FastAPI dashboard app factory."""

from __future__ import annotations

import datetime

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import sessionmaker, Session

from bot.config import AppConfig

_LOCAL_TZ = datetime.datetime.now().astimezone().tzinfo


def _localtime(dt: datetime.datetime | None, fmt: str = "%H:%M") -> str:
    """Convert UTC datetime to local time string."""
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.UTC)
    return dt.astimezone(_LOCAL_TZ).strftime(fmt)


def create_dashboard(
    session_factory: sessionmaker[Session],
    config: AppConfig,
) -> FastAPI:
    app = FastAPI(title="AliBot Dashboard")
    templates = Jinja2Templates(directory="dashboard/templates")
    templates.env.filters["localtime"] = _localtime
    templates.env.filters["localdatetime"] = lambda dt: _localtime(dt, "%d/%m/%Y %H:%M")

    app.state.session_factory = session_factory
    app.state.config = config
    app.state.templates = templates

    from dashboard.routes import register_routes
    register_routes(app)

    return app
