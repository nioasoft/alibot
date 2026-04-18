import pytest
from pathlib import Path


def test_load_config_from_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "1")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
    monkeypatch.setenv("TELEGRAM_PHONE", "+1")
    monkeypatch.setenv("TELEGRAM_ADMIN_USER_ID", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
telegram:
  source_groups:
    - "@test_group"
  manual_source_groups:
    - "manual deals"
  target_groups:
    default: "@my_channel"
  admin_chat: "me"
openai:
  model: "gpt-4o-mini"
publishing:
  min_delay_seconds: 300
  max_delay_seconds: 600
  max_posts_per_hour: 4
  quiet_hours_start: 23
  quiet_hours_end: 7
dedup:
  window_hours: 24
  image_hash_threshold: 5
watermark:
  logo_path: "assets/logo.png"
  position: "bottom-right"
  opacity: 0.4
  scale: 0.15
parser:
  min_message_length: 20
  supported_domains:
    - "aliexpress.com"
dashboard:
  port: 8080
  auto_refresh_seconds: 30
""")
    invite_links_file = tmp_path / "invite-links.json"
    invite_links_file.write_text("[]")
    config_file.write_text(
        config_file.read_text()
        + f"""
marketing:
  site_url: "https://www.dilim.net/"
  invite_links_path: "{invite_links_file.name}"
"""
    )
    from bot.config import load_config

    config = load_config(str(config_file))

    assert config.telegram.source_groups == ["@test_group"]
    assert config.telegram.manual_source_groups == ["manual deals"]
    assert config.openai.model == "gpt-4o-mini"
    assert config.publishing.min_delay_seconds == 300
    assert config.publishing.destinations is not None
    assert config.publishing.destinations["telegram_default"].target == "@my_channel"
    assert config.publishing.destinations["telegram_default"].platform == "telegram"
    assert config.publishing.weekend_reduced_rate_factor == 1.0
    assert config.publishing.weekend_reduced_start_weekday == 4
    assert config.publishing.weekend_reduced_start_hour == 18
    assert config.publishing.weekend_reduced_end_weekday == 5
    assert config.publishing.weekend_reduced_end_hour == 18
    assert config.aliexpress.catalog_account == "primary"
    assert config.aliexpress.affiliate_distribution == {"primary": 100}
    assert config.marketing.site_url == "https://www.dilim.net/"
    assert config.marketing.invite_links == []
    assert config.tracking.base_url == ""
    assert config.tracking.api_secret == ""
    assert config.quality.min_score_external == 70
    assert config.quality.idle_destination_hours == 6
    assert config.quality.min_score_hot_products == 80
    assert config.quality.idle_min_score == 70
    assert config.quality.idle_priority_boost == 150
    assert config.facebook.service_url == "http://localhost:3002"


def test_config_loads_env_vars(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "abc123")
    monkeypatch.setenv("TELEGRAM_PHONE", "+972501234567")
    monkeypatch.setenv("TELEGRAM_ADMIN_USER_ID", "99999")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("ALIEXPRESS_PRIMARY_APP_KEY", "pk")
    monkeypatch.setenv("ALIEXPRESS_PRIMARY_APP_SECRET", "ps")
    monkeypatch.setenv("ALIEXPRESS_PRIMARY_TRACKING_ID", "pt")
    monkeypatch.setenv("ALIEXPRESS_SECONDARY_APP_KEY", "sk")
    monkeypatch.setenv("ALIEXPRESS_SECONDARY_APP_SECRET", "ss")
    monkeypatch.setenv("ALIEXPRESS_SECONDARY_TRACKING_ID", "st")
    monkeypatch.setenv("TRACKING_API_SECRET", "tracker-secret")

    config_file = tmp_path / "config.yaml"
    invite_links_file = tmp_path / "invite-links.json"
    invite_links_file.write_text("""
[
  {
    "url": "https://t.me/test",
    "label": "ערוץ הטלגרם",
    "platform": "telegram",
    "footerLabel": "📢 להצטרפות לטלגרם"
  }
]
""")
    config_file.write_text("""
telegram:
  source_groups: ["@g1"]
  manual_source_groups: ["manual"]
  admin_chat: "me"
marketing:
  site_url: "https://www.dilim.net/"
  invite_links_path: "invite-links.json"
tracking:
  base_url: "https://trk.dilim.net"
openai:
  model: "gpt-4o-mini"
publishing:
  min_delay_seconds: 300
  max_delay_seconds: 600
  max_posts_per_hour: 4
  quiet_hours_start: 23
  quiet_hours_end: 7
  weekend_reduced_rate_factor: 0.3
  weekend_reduced_start_weekday: 4
  weekend_reduced_start_hour: 18
  weekend_reduced_end_weekday: 5
  weekend_reduced_end_hour: 18
  destinations:
    tg_main:
      platform: telegram
      target: "@ch1"
      categories: ["*"]
      min_publish_interval_minutes: 120
dashboard:
  port: 8080
  auto_refresh_seconds: 30
dedup:
  window_hours: 24
  image_hash_threshold: 5
watermark:
  logo_path: "assets/logo.png"
  position: "bottom-right"
  opacity: 0.4
  scale: 0.15
parser:
  min_message_length: 20
  supported_domains: ["aliexpress.com"]
aliexpress:
  catalog_account: secondary
  affiliate_distribution:
    primary: 70
    secondary: 30
quality:
  min_score_external: 50
  min_score_hot_products: 70
  manual_priority: 1234
  idle_destination_hours: 8
  idle_min_score: 25
  idle_priority_boost: 222
""")
    from bot.config import load_config

    config = load_config(str(config_file))

    assert config.telegram.api_id == 12345
    assert config.telegram.api_hash == "abc123"
    assert config.telegram.phone == "+972501234567"
    assert config.telegram.admin_user_id == 99999
    assert config.telegram.manual_source_groups == ["manual"]
    assert config.openai.api_key == "sk-test-key"
    assert config.marketing.site_url == "https://www.dilim.net/"
    assert config.tracking.base_url == "https://trk.dilim.net"
    assert config.tracking.api_secret == "tracker-secret"
    assert len(config.marketing.invite_links) == 1
    assert config.marketing.invite_links[0].platform == "telegram"
    assert config.publishing.destinations["tg_main"].min_publish_interval_minutes == 120
    assert config.publishing.weekend_reduced_rate_factor == 0.3
    assert config.publishing.weekend_reduced_start_weekday == 4
    assert config.publishing.weekend_reduced_start_hour == 18
    assert config.publishing.weekend_reduced_end_weekday == 5
    assert config.publishing.weekend_reduced_end_hour == 18
    assert config.aliexpress.catalog_account == "secondary"
    assert config.aliexpress.accounts["primary"].app_key == "pk"
    assert config.aliexpress.accounts["secondary"].tracking_id == "st"
    assert config.aliexpress.affiliate_distribution == {"primary": 70, "secondary": 30}
    assert config.quality.min_score_external == 50
    assert config.quality.min_score_hot_products == 70
    assert config.quality.manual_priority == 1234
    assert config.quality.idle_destination_hours == 8
    assert config.quality.idle_min_score == 25
    assert config.quality.idle_priority_boost == 222
    assert config.facebook.landing_page_url == ""


def test_config_preserves_numeric_telegram_source_groups(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "abc123")
    monkeypatch.setenv("TELEGRAM_PHONE", "+972501234567")
    monkeypatch.setenv("TELEGRAM_ADMIN_USER_ID", "99999")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
telegram:
  source_groups:
    - "@g1"
    - -5088840057
  manual_source_groups:
    - "הכנסת דילים ידנית"
  admin_chat: "me"
openai:
  model: "gpt-4o-mini"
publishing:
  min_delay_seconds: 300
  max_delay_seconds: 600
  max_posts_per_hour: 4
  quiet_hours_start: 23
  quiet_hours_end: 7
dashboard:
  port: 8080
  auto_refresh_seconds: 30
dedup:
  window_hours: 24
  image_hash_threshold: 5
watermark:
  logo_path: "assets/logo.png"
  position: "bottom-right"
  opacity: 0.4
  scale: 0.15
parser:
  min_message_length: 20
  supported_domains: ["aliexpress.com"]
""")
    from bot.config import load_config

    config = load_config(str(config_file))

    assert config.telegram.source_groups == ["@g1", -5088840057]
    assert config.telegram.manual_source_groups == ["הכנסת דילים ידנית"]
    assert config.marketing.invite_links == []


def test_config_missing_required_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_API_HASH", raising=False)
    monkeypatch.delenv("TELEGRAM_PHONE", raising=False)
    monkeypatch.delenv("TELEGRAM_ADMIN_USER_ID", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
telegram:
  source_groups: ["@g1"]
  admin_chat: "me"
openai:
  model: "gpt-4o-mini"
publishing:
  min_delay_seconds: 300
  max_delay_seconds: 600
  max_posts_per_hour: 4
  quiet_hours_start: 23
  quiet_hours_end: 7
dashboard:
  port: 8080
  auto_refresh_seconds: 30
dedup:
  window_hours: 24
  image_hash_threshold: 5
watermark:
  logo_path: "assets/logo.png"
  position: "bottom-right"
  opacity: 0.4
  scale: 0.15
parser:
  min_message_length: 20
  supported_domains: ["aliexpress.com"]
""")
    from bot.config import load_config

    with pytest.raises(ValueError, match="TELEGRAM_API_ID"):
        load_config(str(config_file))
