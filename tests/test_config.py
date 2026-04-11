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
    from bot.config import load_config

    config = load_config(str(config_file))

    assert config.telegram.source_groups == ["@test_group"]
    assert config.openai.model == "gpt-4o-mini"
    assert config.publishing.min_delay_seconds == 300
    assert config.publishing.destinations is not None
    assert config.publishing.destinations["telegram_default"].target == "@my_channel"
    assert config.publishing.destinations["telegram_default"].platform == "telegram"
    assert config.aliexpress.catalog_account == "primary"
    assert config.aliexpress.affiliate_distribution == {"primary": 100}


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
  destinations:
    tg_main:
      platform: telegram
      target: "@ch1"
      categories: ["*"]
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
""")
    from bot.config import load_config

    config = load_config(str(config_file))

    assert config.telegram.api_id == 12345
    assert config.telegram.api_hash == "abc123"
    assert config.telegram.phone == "+972501234567"
    assert config.telegram.admin_user_id == 99999
    assert config.openai.api_key == "sk-test-key"
    assert config.aliexpress.catalog_account == "secondary"
    assert config.aliexpress.accounts["primary"].app_key == "pk"
    assert config.aliexpress.accounts["secondary"].tracking_id == "st"
    assert config.aliexpress.affiliate_distribution == {"primary": 70, "secondary": 30}


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
