"""Load and validate application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class TelegramConfig:
    api_id: int
    api_hash: str
    phone: str
    admin_user_id: int
    source_groups: list[str]
    target_groups: dict[str, str]
    admin_chat: str
    channel_link: str


@dataclass(frozen=True)
class OpenAIConfig:
    api_key: str
    model: str


@dataclass(frozen=True)
class PublishingConfig:
    min_delay_seconds: int
    max_delay_seconds: int
    max_posts_per_hour: int
    quiet_hours_start: int
    quiet_hours_end: int
    hot_products_interval_hours: int = 4
    hot_products_per_run: int = 3


@dataclass(frozen=True)
class DedupConfig:
    window_hours: int
    image_hash_threshold: int


@dataclass(frozen=True)
class WatermarkConfig:
    logo_path: str
    position: str
    opacity: float
    scale: float


@dataclass(frozen=True)
class ParserConfig:
    min_message_length: int
    supported_domains: list[str]


@dataclass(frozen=True)
class DashboardConfig:
    port: int
    auto_refresh_seconds: int


@dataclass(frozen=True)
class AliExpressConfig:
    app_key: str
    app_secret: str
    tracking_id: str


@dataclass(frozen=True)
class WhatsAppConfig:
    service_url: str
    group_jid: str
    group_link: str


@dataclass(frozen=True)
class AppConfig:
    telegram: TelegramConfig
    openai: OpenAIConfig
    publishing: PublishingConfig
    dedup: DedupConfig
    watermark: WatermarkConfig
    parser: ParserConfig
    dashboard: DashboardConfig
    aliexpress: AliExpressConfig
    whatsapp: WhatsAppConfig


def _require_env(name: str) -> str:
    """Return the value of a required environment variable.

    Raises:
        ValueError: If the environment variable is not set or empty.
    """
    value = os.environ.get(name)
    if not value:
        raise ValueError(
            f"Required environment variable {name} is not set. "
            f"Copy .env.example to .env and fill in the values."
        )
    return value


def load_config(config_path: str) -> AppConfig:
    """Load config from YAML file + environment variables.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Fully populated AppConfig with secrets from environment variables.
    """
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    return AppConfig(
        telegram=TelegramConfig(
            api_id=int(_require_env("TELEGRAM_API_ID")),
            api_hash=_require_env("TELEGRAM_API_HASH"),
            phone=_require_env("TELEGRAM_PHONE"),
            admin_user_id=int(_require_env("TELEGRAM_ADMIN_USER_ID")),
            source_groups=raw["telegram"]["source_groups"],
            target_groups=raw["telegram"]["target_groups"],
            admin_chat=raw["telegram"]["admin_chat"],
            channel_link=raw["telegram"].get("channel_link", ""),
        ),
        openai=OpenAIConfig(
            api_key=_require_env("OPENAI_API_KEY"),
            model=raw["openai"]["model"],
        ),
        publishing=PublishingConfig(
            min_delay_seconds=raw["publishing"]["min_delay_seconds"],
            max_delay_seconds=raw["publishing"]["max_delay_seconds"],
            max_posts_per_hour=raw["publishing"]["max_posts_per_hour"],
            quiet_hours_start=raw["publishing"]["quiet_hours_start"],
            quiet_hours_end=raw["publishing"]["quiet_hours_end"],
            hot_products_interval_hours=raw["publishing"].get("hot_products_interval_hours", 4),
            hot_products_per_run=raw["publishing"].get("hot_products_per_run", 3),
        ),
        dedup=DedupConfig(
            window_hours=raw["dedup"]["window_hours"],
            image_hash_threshold=raw["dedup"]["image_hash_threshold"],
        ),
        watermark=WatermarkConfig(
            logo_path=raw["watermark"]["logo_path"],
            position=raw["watermark"]["position"],
            opacity=raw["watermark"]["opacity"],
            scale=raw["watermark"]["scale"],
        ),
        parser=ParserConfig(
            min_message_length=raw["parser"]["min_message_length"],
            supported_domains=raw["parser"]["supported_domains"],
        ),
        dashboard=DashboardConfig(
            port=raw["dashboard"]["port"],
            auto_refresh_seconds=raw["dashboard"]["auto_refresh_seconds"],
        ),
        aliexpress=AliExpressConfig(
            app_key=os.environ.get("ALIEXPRESS_APP_KEY", ""),
            app_secret=os.environ.get("ALIEXPRESS_APP_SECRET", ""),
            tracking_id=os.environ.get("ALIEXPRESS_TRACKING_ID", ""),
        ),
        whatsapp=WhatsAppConfig(
            service_url=raw.get("whatsapp", {}).get("service_url", "http://localhost:3001"),
            group_jid=raw.get("whatsapp", {}).get("group_jid", ""),
            group_link=raw.get("whatsapp", {}).get("group_link", ""),
        ),
    )
