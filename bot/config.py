"""Load and validate application configuration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class DestinationConfig:
    key: str
    enabled: bool
    platform: str
    target: str
    categories: list[str]
    min_publish_interval_minutes: int = 0


@dataclass(frozen=True)
class TelegramConfig:
    api_id: int
    api_hash: str
    phone: str
    admin_user_id: int
    source_groups: list[str | int]
    manual_source_groups: list[str]
    admin_chat: str
    channel_link: str


@dataclass(frozen=True)
class InviteLinkConfig:
    url: str
    label: str
    platform: str
    footer_label: str


@dataclass(frozen=True)
class MarketingConfig:
    site_url: str
    invite_links_path: str
    invite_links: list[InviteLinkConfig]


@dataclass(frozen=True)
class TrackingConfig:
    base_url: str
    api_secret: str


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
    weekend_reduced_rate_factor: float = 1.0
    weekend_reduced_start_weekday: int = 4
    weekend_reduced_start_hour: int = 18
    weekend_reduced_end_weekday: int = 5
    weekend_reduced_end_hour: int = 18
    destinations: dict[str, DestinationConfig] | None = None


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
class QualityConfig:
    min_score_external: int
    min_score_hot_products: int
    manual_priority: int
    idle_destination_hours: int
    idle_min_score: int
    idle_priority_boost: int


@dataclass(frozen=True)
class DashboardConfig:
    port: int
    auto_refresh_seconds: int


@dataclass(frozen=True)
class AliExpressAccountConfig:
    key: str
    app_key: str
    app_secret: str
    tracking_id: str

    @property
    def is_enabled(self) -> bool:
        return bool(self.app_key and self.app_secret and self.tracking_id)


@dataclass(frozen=True)
class AliExpressConfig:
    accounts: dict[str, AliExpressAccountConfig]
    catalog_account: str
    affiliate_distribution: dict[str, int]


@dataclass(frozen=True)
class WhatsAppConfig:
    service_url: str
    group_link: str


@dataclass(frozen=True)
class FacebookConfig:
    service_url: str
    landing_page_url: str


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    service_key: str


@dataclass(frozen=True)
class AppConfig:
    telegram: TelegramConfig
    marketing: MarketingConfig
    tracking: TrackingConfig
    openai: OpenAIConfig
    publishing: PublishingConfig
    dedup: DedupConfig
    watermark: WatermarkConfig
    parser: ParserConfig
    quality: QualityConfig
    dashboard: DashboardConfig
    aliexpress: AliExpressConfig
    whatsapp: WhatsAppConfig
    facebook: FacebookConfig
    supabase: SupabaseConfig | None = None


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(
            f"Required environment variable {name} is not set. "
            f"Copy .env.example to .env and fill in the values."
        )
    return value


def _optional_env(name: str, fallback: str = "") -> str:
    return os.environ.get(name, fallback)


def _load_destinations(raw: dict) -> dict[str, DestinationConfig]:
    publishing_raw = raw["publishing"]
    raw_destinations = publishing_raw.get("destinations", {})
    destinations: dict[str, DestinationConfig] = {}

    if raw_destinations:
        for key, dest_raw in raw_destinations.items():
            destinations[key] = DestinationConfig(
                key=key,
                enabled=bool(dest_raw.get("enabled", True)),
                platform=str(dest_raw["platform"]),
                target=str(dest_raw["target"]),
                categories=[str(cat) for cat in dest_raw.get("categories", ["other"])],
                min_publish_interval_minutes=max(0, int(dest_raw.get("min_publish_interval_minutes", 0))),
            )
        return destinations

    # Backward-compatible fallback for the old single-platform config.
    for key, target in raw.get("telegram", {}).get("target_groups", {}).items():
        destinations[f"telegram_{key}"] = DestinationConfig(
            key=f"telegram_{key}",
            enabled=True,
            platform="telegram",
            target=str(target),
            categories=["*"] if key == "default" else [str(key)],
        )

    whatsapp_group = raw.get("whatsapp", {}).get("group_jid", "")
    if whatsapp_group:
        destinations["whatsapp_default"] = DestinationConfig(
            key="whatsapp_default",
            enabled=True,
            platform="whatsapp",
            target=str(whatsapp_group),
            categories=["*"],
        )

    return destinations


def _load_aliexpress_config(raw: dict) -> AliExpressConfig:
    ali_raw = raw.get("aliexpress", {})

    primary = AliExpressAccountConfig(
        key="primary",
        app_key=_optional_env("ALIEXPRESS_PRIMARY_APP_KEY", _optional_env("ALIEXPRESS_APP_KEY")),
        app_secret=_optional_env("ALIEXPRESS_PRIMARY_APP_SECRET", _optional_env("ALIEXPRESS_APP_SECRET")),
        tracking_id=_optional_env(
            "ALIEXPRESS_PRIMARY_TRACKING_ID",
            _optional_env("ALIEXPRESS_TRACKING_ID"),
        ),
    )
    secondary = AliExpressAccountConfig(
        key="secondary",
        app_key=_optional_env("ALIEXPRESS_SECONDARY_APP_KEY"),
        app_secret=_optional_env("ALIEXPRESS_SECONDARY_APP_SECRET"),
        tracking_id=_optional_env("ALIEXPRESS_SECONDARY_TRACKING_ID"),
    )

    accounts = {"primary": primary}
    if secondary.app_key or secondary.app_secret or secondary.tracking_id:
        accounts["secondary"] = secondary

    distribution_raw = ali_raw.get("affiliate_distribution", {"primary": 100})
    affiliate_distribution = {
        str(key): max(0, int(value))
        for key, value in distribution_raw.items()
    }

    if sum(affiliate_distribution.values()) <= 0:
        affiliate_distribution = {"primary": 100}

    catalog_account = str(ali_raw.get("catalog_account", "primary"))
    if catalog_account not in accounts:
        catalog_account = "primary"

    return AliExpressConfig(
        accounts=accounts,
        catalog_account=catalog_account,
        affiliate_distribution=affiliate_distribution,
    )


def _load_supabase_config() -> SupabaseConfig | None:
    url = _optional_env("SUPABASE_URL")
    service_key = _optional_env("SUPABASE_SERVICE_KEY")
    if url and service_key:
        return SupabaseConfig(url=url, service_key=service_key)
    return None


def _default_footer_label(platform: str) -> str:
    return {
        "telegram": "📢 להצטרפות לטלגרם",
        "whatsapp": "💬 להצטרפות לוואטסאפ",
        "facebook": "📘 להצטרפות לפייסבוק",
    }.get(platform, "👥 להצטרפות לקבוצה")


def _load_marketing_config(raw: dict, config_dir: Path) -> MarketingConfig:
    marketing_raw = raw.get("marketing", {})
    site_url = str(
        marketing_raw.get(
            "site_url",
            raw.get("facebook", {}).get("landing_page_url", ""),
        )
    ).strip()
    invite_links_path = str(
        marketing_raw.get("invite_links_path", "website/src/data/invite-links.json")
    )

    invite_links: list[InviteLinkConfig] = []
    if invite_links_path:
        resolved_path = (config_dir / invite_links_path).resolve()
        if resolved_path.exists():
            with open(resolved_path, encoding="utf-8") as f:
                raw_links = json.load(f)
            for link_raw in raw_links:
                url = str(link_raw.get("url", "")).strip()
                if not url:
                    continue
                platform = str(link_raw.get("platform", "")).strip()
                invite_links.append(
                    InviteLinkConfig(
                        url=url,
                        label=str(link_raw.get("label", "")).strip() or url,
                        platform=platform,
                        footer_label=str(
                            link_raw.get("footerLabel", _default_footer_label(platform))
                        ).strip(),
                    )
                )

    return MarketingConfig(
        site_url=site_url,
        invite_links_path=invite_links_path,
        invite_links=invite_links,
    )


def _load_tracking_config(raw: dict) -> TrackingConfig:
    tracking_raw = raw.get("tracking", {})
    return TrackingConfig(
        base_url=str(tracking_raw.get("base_url", "")).strip().rstrip("/"),
        api_secret=_optional_env("TRACKING_API_SECRET").strip(),
    )


def load_config(config_path: str) -> AppConfig:
    config_file = Path(config_path).resolve()
    with open(config_file, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return AppConfig(
        telegram=TelegramConfig(
            api_id=int(_require_env("TELEGRAM_API_ID")),
            api_hash=_require_env("TELEGRAM_API_HASH"),
            phone=_require_env("TELEGRAM_PHONE"),
            admin_user_id=int(_require_env("TELEGRAM_ADMIN_USER_ID")),
            source_groups=[
                group if isinstance(group, int) else str(group)
                for group in raw["telegram"]["source_groups"]
            ],
            manual_source_groups=[
                str(group)
                for group in raw.get("telegram", {}).get("manual_source_groups", [])
            ],
            admin_chat=raw["telegram"]["admin_chat"],
            channel_link=raw["telegram"].get("channel_link", ""),
        ),
        marketing=_load_marketing_config(raw, config_file.parent),
        tracking=_load_tracking_config(raw),
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
            weekend_reduced_rate_factor=float(raw["publishing"].get("weekend_reduced_rate_factor", 1.0)),
            weekend_reduced_start_weekday=int(raw["publishing"].get("weekend_reduced_start_weekday", 4)),
            weekend_reduced_start_hour=int(raw["publishing"].get("weekend_reduced_start_hour", 18)),
            weekend_reduced_end_weekday=int(raw["publishing"].get("weekend_reduced_end_weekday", 5)),
            weekend_reduced_end_hour=int(raw["publishing"].get("weekend_reduced_end_hour", 18)),
            destinations=_load_destinations(raw),
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
        quality=QualityConfig(
            min_score_external=int(raw.get("quality", {}).get("min_score_external", 70)),
            min_score_hot_products=int(raw.get("quality", {}).get("min_score_hot_products", 80)),
            manual_priority=int(raw.get("quality", {}).get("manual_priority", 1000)),
            idle_destination_hours=int(raw.get("quality", {}).get("idle_destination_hours", 6)),
            idle_min_score=int(raw.get("quality", {}).get("idle_min_score", 70)),
            idle_priority_boost=int(raw.get("quality", {}).get("idle_priority_boost", 150)),
        ),
        dashboard=DashboardConfig(
            port=raw["dashboard"]["port"],
            auto_refresh_seconds=raw["dashboard"]["auto_refresh_seconds"],
        ),
        aliexpress=_load_aliexpress_config(raw),
        whatsapp=WhatsAppConfig(
            service_url=raw.get("whatsapp", {}).get("service_url", "http://localhost:3001"),
            group_link=raw.get("whatsapp", {}).get("group_link", ""),
        ),
        facebook=FacebookConfig(
            service_url=raw.get("facebook", {}).get("service_url", "http://localhost:3002"),
            landing_page_url=raw.get("facebook", {}).get("landing_page_url", ""),
        ),
        supabase=_load_supabase_config(),
    )
