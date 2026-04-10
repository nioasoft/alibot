"""FastAPI dashboard app factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import sessionmaker, Session

from bot.config import AppConfig


def create_dashboard(
    session_factory: sessionmaker[Session],
    config: AppConfig,
) -> FastAPI:
    app = FastAPI(title="AliBot Dashboard")
    templates = Jinja2Templates(directory="dashboard/templates")

    app.state.session_factory = session_factory
    app.state.config = config
    app.state.templates = templates

    from dashboard.routes import register_routes
    register_routes(app)

    return app
