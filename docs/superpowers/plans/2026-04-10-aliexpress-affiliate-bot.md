# AliExpress Affiliate Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automated Telegram bot that listens to Hebrew deal groups, deduplicates, rewrites with AI, adds watermark, and publishes to our channel at a controlled pace.

**Architecture:** Single async Python process with two loops — an event-driven processing loop (Telethon listener → parser → dedup → resolver → rewriter → image processor → DB queue) and a scheduled publishing loop (APScheduler picks from queue, publishes with rate limiting). Web dashboard via FastAPI on same process.

**Tech Stack:** Python 3.10+, Telethon, SQLAlchemy 2.0, httpx, openai, Pillow, imagehash, APScheduler 3.x, FastAPI, Jinja2, Tailwind CSS, loguru, pytest

---

## File Map

### Phase 1a — Core Pipeline

| File | Action | Responsibility |
|------|--------|----------------|
| `requirements.txt` | Create | All dependencies |
| `.env.example` | Create | Environment variable template |
| `.gitignore` | Create | Ignore patterns |
| `config.yaml` | Create | Application configuration |
| `bot/__init__.py` | Create | Package init |
| `bot/config.py` | Create | Load YAML, substitute env vars, validate |
| `bot/models.py` | Create | SQLAlchemy ORM models (4 tables) |
| `bot/parser.py` | Create | Extract links, prices, product info |
| `bot/resolver.py` | Create | Resolve short URLs → product IDs |
| `bot/dedup.py` | Create | 3-layer duplicate detection |
| `bot/rewriter.py` | Create | OpenAI rewrite + categorize |
| `bot/image_processor.py` | Create | Watermark overlay on images |
| `bot/pipeline.py` | Create | Orchestrate processing stages |
| `bot/publisher.py` | Create | Queue-based publisher with rate limits |
| `bot/notifier.py` | Create | Error alerts + daily summary |
| `bot/admin.py` | Create | Telegram admin commands |
| `bot/listener.py` | Create | Telethon event handler |
| `main.py` | Create | Entry point, wire everything |
| `tests/__init__.py` | Create | Test package |
| `tests/conftest.py` | Create | Shared fixtures (DB, mocks) |
| `tests/test_config.py` | Create | Config loading tests |
| `tests/test_parser.py` | Create | Parser tests |
| `tests/test_resolver.py` | Create | Resolver tests |
| `tests/test_dedup.py` | Create | Dedup tests |
| `tests/test_rewriter.py` | Create | Rewriter tests |
| `tests/test_image_processor.py` | Create | Image processor tests |
| `tests/test_pipeline.py` | Create | Pipeline integration tests |
| `tests/test_publisher.py` | Create | Publisher queue logic tests |

### Phase 1b — Web Dashboard

| File | Action | Responsibility |
|------|--------|----------------|
| `dashboard/__init__.py` | Create | Package init |
| `dashboard/app.py` | Create | FastAPI app factory |
| `dashboard/routes.py` | Create | All route handlers |
| `dashboard/templates/base.html` | Create | RTL base template + Tailwind |
| `dashboard/templates/index.html` | Create | Main dashboard |
| `dashboard/templates/deals.html` | Create | Deal list with filters |
| `dashboard/templates/deal_detail.html` | Create | Single deal view |
| `dashboard/templates/queue.html` | Create | Publish queue management |
| `dashboard/templates/settings.html` | Create | Config viewer |
| `dashboard/templates/logs.html` | Create | Log viewer |

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `config.yaml`
- Create: `bot/__init__.py`
- Create: `tests/__init__.py`
- Create: `data/.gitkeep`
- Create: `data/images/.gitkeep`
- Create: `assets/.gitkeep`

- [ ] **Step 1: Create requirements.txt**

```
# Telegram
telethon>=1.36,<2.0

# Database
sqlalchemy>=2.0,<3.0

# HTTP
httpx>=0.27

# AI
openai>=1.50

# Image processing
Pillow>=10.0
imagehash>=4.3

# Scheduling
APScheduler>=3.10,<4.0

# Web dashboard
fastapi>=0.115
jinja2>=3.1
uvicorn>=0.32

# Config & utils
pyyaml>=6.0
loguru>=0.7
python-dotenv>=1.0

# Testing
pytest>=8.0
pytest-asyncio>=0.24
respx>=0.22
```

- [ ] **Step 2: Create .env.example**

```
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=+972XXXXXXXXX
TELEGRAM_ADMIN_USER_ID=

OPENAI_API_KEY=

# Phase 2 — AliExpress API
# ALIEXPRESS_APP_KEY=
# ALIEXPRESS_APP_SECRET=
# ALIEXPRESS_TRACKING_ID=
```

- [ ] **Step 3: Create .gitignore**

```
__pycache__/
*.py[cod]
*.so
.env
*.session
*.session-journal
data/deals.db
data/images/*
!data/images/.gitkeep
assets/logo.png
.venv/
venv/
dist/
*.egg-info/
.pytest_cache/
.mypy_cache/
```

- [ ] **Step 4: Create config.yaml**

```yaml
telegram:
  source_groups:
    - "@group1"
    - "@group2"

  target_groups:
    default: "@my_deals_channel"

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
    - "s.click.aliexpress.com"
    - "a.aliexpress.com"

dashboard:
  port: 8080
  auto_refresh_seconds: 30
```

- [ ] **Step 5: Create empty package files and data directories**

```bash
mkdir -p bot tests data/images assets dashboard/templates
touch bot/__init__.py tests/__init__.py dashboard/__init__.py
touch data/.gitkeep data/images/.gitkeep assets/.gitkeep
```

- [ ] **Step 6: Initialize git and commit**

```bash
git init
git add -A
git commit -m "chore: project scaffolding with dependencies and config"
```

---

### Task 2: Configuration System

**Files:**
- Create: `bot/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for config loading**

File: `tests/test_config.py`

```python
import os
import pytest
from pathlib import Path


def test_load_config_from_yaml(tmp_path: Path):
    """Config loads values from YAML file."""
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
    assert config.telegram.target_groups == {"default": "@my_channel"}
    assert config.openai.model == "gpt-4o-mini"
    assert config.publishing.min_delay_seconds == 300
    assert config.publishing.quiet_hours_start == 23
    assert config.dedup.window_hours == 24
    assert config.watermark.opacity == 0.4
    assert config.parser.min_message_length == 20
    assert config.dashboard.port == 8080


def test_config_loads_env_vars(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Secrets come from environment variables, not YAML."""
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "abc123")
    monkeypatch.setenv("TELEGRAM_PHONE", "+972501234567")
    monkeypatch.setenv("TELEGRAM_ADMIN_USER_ID", "99999")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
telegram:
  source_groups: ["@g1"]
  target_groups:
    default: "@ch1"
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
  supported_domains: ["aliexpress.com"]
dashboard:
  port: 8080
  auto_refresh_seconds: 30
""")
    from bot.config import load_config

    config = load_config(str(config_file))

    assert config.telegram.api_id == 12345
    assert config.telegram.api_hash == "abc123"
    assert config.telegram.phone == "+972501234567"
    assert config.telegram.admin_user_id == 99999
    assert config.openai.api_key == "sk-test-key"


def test_config_missing_required_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Missing required env var raises clear error."""
    monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_API_HASH", raising=False)
    monkeypatch.delenv("TELEGRAM_PHONE", raising=False)
    monkeypatch.delenv("TELEGRAM_ADMIN_USER_ID", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
telegram:
  source_groups: ["@g1"]
  target_groups:
    default: "@ch1"
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
  supported_domains: ["aliexpress.com"]
dashboard:
  port: 8080
  auto_refresh_seconds: 30
""")
    from bot.config import load_config

    with pytest.raises(ValueError, match="TELEGRAM_API_ID"):
        load_config(str(config_file))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/asafbenatia/Projects/_personal/alibot
python -m pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'bot.config'`

- [ ] **Step 3: Implement bot/config.py**

```python
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
class AppConfig:
    telegram: TelegramConfig
    openai: OpenAIConfig
    publishing: PublishingConfig
    dedup: DedupConfig
    watermark: WatermarkConfig
    parser: ParserConfig
    dashboard: DashboardConfig


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(
            f"Required environment variable {name} is not set. "
            f"Copy .env.example to .env and fill in the values."
        )
    return value


def load_config(config_path: str) -> AppConfig:
    """Load config from YAML file + environment variables."""
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
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_config.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bot/config.py tests/test_config.py
git commit -m "feat: configuration system with YAML + env var loading"
```

---

### Task 3: Database Models

**Files:**
- Create: `bot/models.py`
- Create: `tests/conftest.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for models**

File: `tests/test_models.py`

```python
import datetime
from sqlalchemy import select
from bot.models import RawMessage, Deal, PublishQueueItem, DailyStat


def test_create_raw_message(db_session):
    msg = RawMessage(
        source_group="@test_group",
        telegram_message_id=12345,
        raw_text="Great deal! https://s.click.aliexpress.com/e/_abc123",
        has_images=True,
        received_at=datetime.datetime.now(datetime.UTC),
        status="pending",
    )
    db_session.add(msg)
    db_session.commit()

    result = db_session.execute(select(RawMessage)).scalar_one()
    assert result.source_group == "@test_group"
    assert result.status == "pending"
    assert result.telegram_message_id == 12345


def test_create_deal_linked_to_raw_message(db_session):
    msg = RawMessage(
        source_group="@test",
        telegram_message_id=1,
        raw_text="text",
        has_images=False,
        received_at=datetime.datetime.now(datetime.UTC),
        status="processed",
    )
    db_session.add(msg)
    db_session.flush()

    deal = Deal(
        raw_message_id=msg.id,
        product_id="1005003091506814",
        product_name="Wireless Earbuds",
        original_text="Original deal text",
        rewritten_text="Rewritten text",
        price=45.90,
        currency="ILS",
        category="tech",
        product_link="https://aliexpress.com/item/1005003091506814.html",
        text_hash="abc123hash",
        source_group="@test",
        created_at=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(deal)
    db_session.commit()

    result = db_session.execute(select(Deal)).scalar_one()
    assert result.product_id == "1005003091506814"
    assert result.raw_message_id == msg.id
    assert result.price == 45.90


def test_create_publish_queue_item(db_session):
    msg = RawMessage(
        source_group="@test",
        telegram_message_id=1,
        raw_text="text",
        has_images=False,
        received_at=datetime.datetime.now(datetime.UTC),
        status="processed",
    )
    db_session.add(msg)
    db_session.flush()

    deal = Deal(
        raw_message_id=msg.id,
        product_name="Test",
        original_text="orig",
        rewritten_text="new",
        price=10.0,
        currency="ILS",
        category="tech",
        product_link="https://aliexpress.com/item/123.html",
        text_hash="hash1",
        source_group="@test",
        created_at=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(deal)
    db_session.flush()

    queue_item = PublishQueueItem(
        deal_id=deal.id,
        target_group="@my_channel",
        status="queued",
        scheduled_after=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(queue_item)
    db_session.commit()

    result = db_session.execute(select(PublishQueueItem)).scalar_one()
    assert result.status == "queued"
    assert result.deal_id == deal.id


def test_daily_stats_upsert(db_session):
    today = datetime.date.today()
    stat = DailyStat(
        date=today,
        deals_seen=10,
        deals_processed=8,
        deals_published=5,
        deals_skipped_dup=2,
        deals_skipped_error=1,
        api_calls=8,
    )
    db_session.add(stat)
    db_session.commit()

    result = db_session.execute(
        select(DailyStat).where(DailyStat.date == today)
    ).scalar_one()
    assert result.deals_seen == 10
    assert result.deals_published == 5
```

- [ ] **Step 2: Create conftest.py with DB fixture**

File: `tests/conftest.py`

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from bot.models import Base


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Session:
    session_factory = sessionmaker(bind=db_engine)
    session = session_factory()
    yield session
    session.close()
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python -m pytest tests/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'bot.models'`

- [ ] **Step 4: Implement bot/models.py**

```python
"""SQLAlchemy ORM models for the deal pipeline."""

from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import Index, ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session


class Base(DeclarativeBase):
    pass


class RawMessage(Base):
    __tablename__ = "raw_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_group: Mapped[str]
    telegram_message_id: Mapped[int]
    raw_text: Mapped[str]
    has_images: Mapped[bool]
    received_at: Mapped[datetime.datetime]
    status: Mapped[str]  # pending / processed / failed
    error_message: Mapped[Optional[str]]


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_message_id: Mapped[int] = mapped_column(ForeignKey("raw_messages.id"))
    product_id: Mapped[Optional[str]] = mapped_column(unique=True)
    product_name: Mapped[str]
    original_text: Mapped[str]
    rewritten_text: Mapped[str]
    price: Mapped[float]
    original_price: Mapped[Optional[float]]
    currency: Mapped[str]
    shipping: Mapped[Optional[str]]
    category: Mapped[str]
    affiliate_link: Mapped[Optional[str]]
    product_link: Mapped[str]
    image_hash: Mapped[Optional[str]]
    image_path: Mapped[Optional[str]]  # path to processed image on disk
    text_hash: Mapped[str]
    source_group: Mapped[str]
    created_at: Mapped[datetime.datetime]

    __table_args__ = (
        Index("idx_deals_image_hash", "image_hash"),
        Index("idx_deals_text_hash", "text_hash"),
        Index("idx_deals_created_at", "created_at"),
    )


class PublishQueueItem(Base):
    __tablename__ = "publish_queue"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id"))
    target_group: Mapped[str]
    status: Mapped[str]  # queued / publishing / published / failed
    priority: Mapped[int] = mapped_column(default=0)
    scheduled_after: Mapped[datetime.datetime]
    published_at: Mapped[Optional[datetime.datetime]]
    message_id: Mapped[Optional[int]]
    error_message: Mapped[Optional[str]]

    __table_args__ = (
        Index("idx_queue_status_scheduled", "status", "scheduled_after"),
    )


class DailyStat(Base):
    __tablename__ = "daily_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime.date] = mapped_column(unique=True)
    deals_seen: Mapped[int] = mapped_column(default=0)
    deals_processed: Mapped[int] = mapped_column(default=0)
    deals_published: Mapped[int] = mapped_column(default=0)
    deals_skipped_dup: Mapped[int] = mapped_column(default=0)
    deals_skipped_error: Mapped[int] = mapped_column(default=0)
    api_calls: Mapped[int] = mapped_column(default=0)


def init_db(db_path: str) -> sessionmaker[Session]:
    """Create engine, ensure tables exist, return session factory."""
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_models.py -v
```

Expected: 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add bot/models.py tests/conftest.py tests/test_models.py
git commit -m "feat: SQLAlchemy models for raw_messages, deals, publish_queue, daily_stats"
```

---

### Task 4: Message Parser

**Files:**
- Create: `bot/parser.py`
- Create: `tests/test_parser.py`

- [ ] **Step 1: Write failing tests for parser**

File: `tests/test_parser.py`

```python
import pytest
from bot.parser import DealParser, ParsedDeal


@pytest.fixture
def parser():
    return DealParser(
        min_message_length=20,
        supported_domains=["aliexpress.com", "s.click.aliexpress.com", "a.aliexpress.com"],
    )


class TestLinkExtraction:
    def test_extract_short_link(self, parser: DealParser):
        text = "Amazing deal! https://s.click.aliexpress.com/e/_oEhUSd4 only 29 ILS"
        result = parser.parse(text)
        assert result is not None
        assert result.link == "https://s.click.aliexpress.com/e/_oEhUSd4"

    def test_extract_direct_product_link(self, parser: DealParser):
        text = "Check this out https://www.aliexpress.com/item/1005003091506814.html great price"
        result = parser.parse(text)
        assert result is not None
        assert result.link == "https://www.aliexpress.com/item/1005003091506814.html"
        assert result.product_id == "1005003091506814"

    def test_extract_link_with_query_params(self, parser: DealParser):
        text = "Deal https://www.aliexpress.com/item/1005003091506814.html?spm=abc&algo=xyz only today"
        result = parser.parse(text)
        assert result is not None
        assert result.product_id == "1005003091506814"

    def test_no_aliexpress_link_returns_none(self, parser: DealParser):
        text = "This is a deal from Amazon https://amazon.com/dp/B09XYZ nice stuff"
        result = parser.parse(text)
        assert result is None

    def test_a_aliexpress_domain(self, parser: DealParser):
        text = "Great price https://a.aliexpress.com/_mK1abc2 go buy it"
        result = parser.parse(text)
        assert result is not None
        assert result.link == "https://a.aliexpress.com/_mK1abc2"


class TestPriceExtraction:
    def test_extract_price_ils_symbol(self, parser: DealParser):
        text = "Wireless earbuds https://s.click.aliexpress.com/e/_abc only ₪45.90!"
        result = parser.parse(text)
        assert result is not None
        assert result.price == 45.90
        assert result.currency == "ILS"

    def test_extract_price_shekel_text(self, parser: DealParser):
        text = 'Gadget https://s.click.aliexpress.com/e/_abc 29 ש"ח with free shipping'
        result = parser.parse(text)
        assert result is not None
        assert result.price == 29.0
        assert result.currency == "ILS"

    def test_extract_price_usd(self, parser: DealParser):
        text = "Nice item https://s.click.aliexpress.com/e/_abc $12.99 shipped"
        result = parser.parse(text)
        assert result is not None
        assert result.price == 12.99
        assert result.currency == "USD"

    def test_extract_price_with_original(self, parser: DealParser):
        text = "Was ₪89 now ₪45! https://s.click.aliexpress.com/e/_abc huge discount"
        result = parser.parse(text)
        assert result is not None
        assert result.price == 45.0
        assert result.original_price == 89.0

    def test_no_price_still_parses(self, parser: DealParser):
        text = "Amazing product check it out https://s.click.aliexpress.com/e/_abc"
        result = parser.parse(text)
        assert result is not None
        assert result.price is None


class TestFiltering:
    def test_short_message_returns_none(self, parser: DealParser):
        text = "short"
        result = parser.parse(text)
        assert result is None

    def test_message_without_link_returns_none(self, parser: DealParser):
        text = "This is a long message about deals but has no actual link to anything"
        result = parser.parse(text)
        assert result is None


class TestShippingExtraction:
    def test_extract_free_shipping(self, parser: DealParser):
        text = "Earbuds ₪45 https://s.click.aliexpress.com/e/_abc משלוח חינם"
        result = parser.parse(text)
        assert result is not None
        assert result.shipping == "חינם"

    def test_extract_free_shipping_english(self, parser: DealParser):
        text = "Earbuds ₪45 https://s.click.aliexpress.com/e/_abc free shipping!"
        result = parser.parse(text)
        assert result is not None
        assert result.shipping == "חינם"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_parser.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'bot.parser'`

- [ ] **Step 3: Implement bot/parser.py**

```python
"""Parse deal messages to extract links, prices, and product info."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedDeal:
    link: str
    product_id: Optional[str]
    price: Optional[float]
    original_price: Optional[float]
    currency: Optional[str]
    shipping: Optional[str]
    raw_text: str


# Regex patterns
_ALIEXPRESS_URL = re.compile(
    r"https?://(?:www\.)?"
    r"(?:s\.click\.aliexpress\.com/e/[A-Za-z0-9_-]+"
    r"|a\.aliexpress\.com/[A-Za-z0-9_-]+"
    r"|(?:\w+\.)?aliexpress\.com/item/(\d+)\.html[^\s]*)",
    re.IGNORECASE,
)

_PRICE_ILS = re.compile(
    r"(?:₪|nis|ils)\s*(\d+(?:[.,]\d+)?)"
    r"|(\d+(?:[.,]\d+)?)\s*(?:₪|ש\"ח|שח|nis|ils)",
    re.IGNORECASE,
)

_PRICE_USD = re.compile(
    r"\$\s*(\d+(?:[.,]\d+)?)"
    r"|(\d+(?:[.,]\d+)?)\s*(?:usd|\$)",
    re.IGNORECASE,
)

_FREE_SHIPPING = re.compile(
    r"משלוח\s*חינם|free\s*shipping|חינם\s*משלוח",
    re.IGNORECASE,
)

_PRODUCT_ID_FROM_URL = re.compile(r"/item/(\d+)\.html", re.IGNORECASE)


def _parse_price_value(match: re.Match) -> float:
    raw = match.group(1) or match.group(2)
    return float(raw.replace(",", "."))


class DealParser:
    def __init__(self, min_message_length: int, supported_domains: list[str]):
        self._min_length = min_message_length
        self._domains = supported_domains

    def parse(self, text: str) -> Optional[ParsedDeal]:
        if len(text) < self._min_length:
            return None

        link_match = _ALIEXPRESS_URL.search(text)
        if link_match is None:
            return None

        link = link_match.group(0)
        # Strip trailing punctuation that got captured
        link = link.rstrip(".,!?)")

        # Extract product ID from direct links
        product_id = None
        pid_match = _PRODUCT_ID_FROM_URL.search(link)
        if pid_match:
            product_id = pid_match.group(1)

        # Extract prices (all ILS matches, then USD)
        prices = self._extract_prices(text)
        price = prices.get("price")
        original_price = prices.get("original_price")
        currency = prices.get("currency")

        # Extract shipping
        shipping = None
        if _FREE_SHIPPING.search(text):
            shipping = "חינם"

        return ParsedDeal(
            link=link,
            product_id=product_id,
            price=price,
            original_price=original_price,
            currency=currency,
            shipping=shipping,
            raw_text=text,
        )

    def _extract_prices(self, text: str) -> dict:
        # Try ILS first (more common in Hebrew deal groups)
        ils_matches = list(_PRICE_ILS.finditer(text))
        if ils_matches:
            values = sorted([_parse_price_value(m) for m in ils_matches])
            if len(values) >= 2:
                return {
                    "price": values[0],
                    "original_price": values[-1],
                    "currency": "ILS",
                }
            return {"price": values[0], "original_price": None, "currency": "ILS"}

        # Try USD
        usd_matches = list(_PRICE_USD.finditer(text))
        if usd_matches:
            values = sorted([_parse_price_value(m) for m in usd_matches])
            if len(values) >= 2:
                return {
                    "price": values[0],
                    "original_price": values[-1],
                    "currency": "USD",
                }
            return {"price": values[0], "original_price": None, "currency": "USD"}

        return {"price": None, "original_price": None, "currency": None}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_parser.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add bot/parser.py tests/test_parser.py
git commit -m "feat: message parser with link, price, and shipping extraction"
```

---

### Task 5: Link Resolver

**Files:**
- Create: `bot/resolver.py`
- Create: `tests/test_resolver.py`

- [ ] **Step 1: Write failing tests for resolver**

File: `tests/test_resolver.py`

```python
import pytest
import httpx
import respx

from bot.resolver import LinkResolver


@pytest.fixture
def resolver():
    return LinkResolver()


@pytest.mark.asyncio
class TestLinkResolver:
    async def test_resolve_short_link_to_product_id(self, resolver: LinkResolver):
        short_url = "https://s.click.aliexpress.com/e/_oEhUSd4"
        final_url = "https://www.aliexpress.com/item/1005003091506814.html?algo_pvid=abc"

        with respx.mock:
            respx.get(short_url).mock(
                return_value=httpx.Response(
                    302,
                    headers={"Location": final_url},
                )
            )
            respx.get(final_url).mock(
                return_value=httpx.Response(200)
            )

            product_id = await resolver.resolve(short_url)

        assert product_id == "1005003091506814"

    async def test_direct_link_extracts_product_id(self, resolver: LinkResolver):
        url = "https://www.aliexpress.com/item/1005006789012345.html"
        product_id = await resolver.resolve(url)
        assert product_id == "1005006789012345"

    async def test_timeout_returns_none(self, resolver: LinkResolver):
        short_url = "https://s.click.aliexpress.com/e/_timeout"

        with respx.mock:
            respx.get(short_url).mock(side_effect=httpx.ReadTimeout("timeout"))

            product_id = await resolver.resolve(short_url)

        assert product_id is None

    async def test_cache_avoids_second_request(self, resolver: LinkResolver):
        short_url = "https://s.click.aliexpress.com/e/_cached"
        final_url = "https://www.aliexpress.com/item/9999999999.html"

        with respx.mock:
            route = respx.get(short_url).mock(
                return_value=httpx.Response(
                    302,
                    headers={"Location": final_url},
                )
            )
            respx.get(final_url).mock(return_value=httpx.Response(200))

            await resolver.resolve(short_url)
            await resolver.resolve(short_url)

        assert route.call_count == 1

    async def test_non_aliexpress_redirect_returns_none(self, resolver: LinkResolver):
        short_url = "https://s.click.aliexpress.com/e/_weird"
        final_url = "https://some-other-site.com/page"

        with respx.mock:
            respx.get(short_url).mock(
                return_value=httpx.Response(
                    302,
                    headers={"Location": final_url},
                )
            )
            respx.get(final_url).mock(return_value=httpx.Response(200))

            product_id = await resolver.resolve(short_url)

        assert product_id is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_resolver.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'bot.resolver'`

- [ ] **Step 3: Implement bot/resolver.py**

```python
"""Resolve AliExpress short links to product IDs."""

from __future__ import annotations

import re
from typing import Optional

import httpx
from loguru import logger

_PRODUCT_ID_PATTERN = re.compile(r"/item/(\d+)\.html")


class LinkResolver:
    def __init__(self, timeout: float = 10.0):
        self._timeout = timeout
        self._cache: dict[str, Optional[str]] = {}

    async def resolve(self, url: str) -> Optional[str]:
        # Check if it's already a direct product link
        direct_match = _PRODUCT_ID_PATTERN.search(url)
        if direct_match:
            return direct_match.group(1)

        # Check cache
        if url in self._cache:
            return self._cache[url]

        # Follow redirects
        product_id = await self._follow_redirects(url)
        self._cache[url] = product_id
        return product_id

    async def _follow_redirects(self, url: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=self._timeout,
            ) as client:
                response = await client.get(url)
                final_url = str(response.url)

                match = _PRODUCT_ID_PATTERN.search(final_url)
                if match:
                    return match.group(1)

                logger.warning(f"Resolved URL has no product ID: {final_url}")
                return None

        except httpx.TimeoutException:
            logger.error(f"Timeout resolving link: {url}")
            return None
        except httpx.HTTPError as e:
            logger.error(f"HTTP error resolving link {url}: {e}")
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_resolver.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add bot/resolver.py tests/test_resolver.py
git commit -m "feat: link resolver with redirect following and caching"
```

---

### Task 6: Duplicate Checker

**Files:**
- Create: `bot/dedup.py`
- Create: `tests/test_dedup.py`

- [ ] **Step 1: Write failing tests for dedup**

File: `tests/test_dedup.py`

```python
import datetime
import hashlib
import pytest
from unittest.mock import MagicMock

from bot.dedup import DuplicateChecker
from bot.models import Deal


@pytest.fixture
def dedup(db_session):
    return DuplicateChecker(session=db_session, window_hours=24, image_hash_threshold=5)


def _make_deal(db_session, **overrides) -> Deal:
    defaults = dict(
        raw_message_id=1,
        product_name="Test Product",
        original_text="orig",
        rewritten_text="new",
        price=10.0,
        currency="ILS",
        category="tech",
        product_link="https://aliexpress.com/item/123.html",
        text_hash=hashlib.md5(b"test product").hexdigest(),
        source_group="@test",
        created_at=datetime.datetime.now(datetime.UTC),
    )
    defaults.update(overrides)
    deal = Deal(**defaults)
    db_session.add(deal)
    db_session.commit()
    return deal


class TestProductIdDedup:
    def test_same_product_id_is_duplicate(self, dedup: DuplicateChecker, db_session):
        _make_deal(db_session, product_id="12345")
        assert dedup.is_duplicate(product_id="12345") is True

    def test_different_product_id_not_duplicate(self, dedup: DuplicateChecker, db_session):
        _make_deal(db_session, product_id="12345")
        assert dedup.is_duplicate(product_id="99999") is False

    def test_none_product_id_skips_check(self, dedup: DuplicateChecker):
        assert dedup.is_duplicate(product_id=None) is False


class TestTextHashDedup:
    def test_same_text_hash_is_duplicate(self, dedup: DuplicateChecker, db_session):
        text_hash = hashlib.md5(b"wireless earbuds bluetooth").hexdigest()
        _make_deal(db_session, product_id=None, text_hash=text_hash)
        assert dedup.is_duplicate(text_hash=text_hash) is True

    def test_different_text_hash_not_duplicate(self, dedup: DuplicateChecker, db_session):
        _make_deal(db_session, product_id=None, text_hash="aaa")
        assert dedup.is_duplicate(text_hash="bbb") is False


class TestImageHashDedup:
    def test_similar_image_hash_is_duplicate(self, dedup: DuplicateChecker, db_session):
        # dhash values: "0a1b2c3d4e5f6a7b" vs "0a1b2c3d4e5f6a7c" → hamming distance 1
        _make_deal(db_session, product_id=None, image_hash="0a1b2c3d4e5f6a7b")
        assert dedup.is_duplicate(image_hash="0a1b2c3d4e5f6a7c") is True

    def test_very_different_image_hash_not_duplicate(self, dedup: DuplicateChecker, db_session):
        _make_deal(db_session, product_id=None, image_hash="0000000000000000")
        assert dedup.is_duplicate(image_hash="ffffffffffffffff") is False


class TestWindowExpiry:
    def test_old_deal_outside_window_not_duplicate(self, dedup: DuplicateChecker, db_session):
        old_time = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=25)
        _make_deal(db_session, product_id="old_deal", created_at=old_time)
        assert dedup.is_duplicate(product_id="old_deal") is False


class TestCleanup:
    def test_cleanup_removes_old_entries(self, dedup: DuplicateChecker, db_session):
        old_time = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=25)
        _make_deal(db_session, product_id="old1", created_at=old_time)
        _make_deal(db_session, product_id="new1", created_at=datetime.datetime.now(datetime.UTC))

        from sqlalchemy import select, func
        from bot.models import Deal
        count_before = db_session.execute(select(func.count()).select_from(Deal)).scalar()
        assert count_before == 2

        dedup.cleanup_old()

        count_after = db_session.execute(select(func.count()).select_from(Deal)).scalar()
        assert count_after == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_dedup.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'bot.dedup'`

- [ ] **Step 3: Implement bot/dedup.py**

```python
"""Three-layer duplicate detection for deals."""

from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from loguru import logger

from bot.models import Deal


def _hamming_distance(hash1: str, hash2: str) -> int:
    """Compute hamming distance between two hex hash strings."""
    n1 = int(hash1, 16)
    n2 = int(hash2, 16)
    return bin(n1 ^ n2).count("1")


class DuplicateChecker:
    def __init__(self, session: Session, window_hours: int, image_hash_threshold: int):
        self._session = session
        self._window_hours = window_hours
        self._image_hash_threshold = image_hash_threshold

    def _cutoff(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.UTC) - datetime.timedelta(
            hours=self._window_hours
        )

    def is_duplicate(
        self,
        product_id: Optional[str] = None,
        text_hash: Optional[str] = None,
        image_hash: Optional[str] = None,
    ) -> bool:
        cutoff = self._cutoff()

        # Layer 1: Product ID exact match
        if product_id is not None:
            exists = self._session.execute(
                select(Deal.id).where(
                    Deal.product_id == product_id,
                    Deal.created_at >= cutoff,
                )
            ).first()
            if exists:
                logger.debug(f"Duplicate: product_id={product_id}")
                return True

        # Layer 2: Text hash exact match
        if text_hash is not None:
            exists = self._session.execute(
                select(Deal.id).where(
                    Deal.text_hash == text_hash,
                    Deal.created_at >= cutoff,
                )
            ).first()
            if exists:
                logger.debug(f"Duplicate: text_hash={text_hash}")
                return True

        # Layer 3: Image perceptual hash similarity
        if image_hash is not None:
            recent_hashes = self._session.execute(
                select(Deal.image_hash).where(
                    Deal.image_hash.isnot(None),
                    Deal.created_at >= cutoff,
                )
            ).scalars().all()

            for existing_hash in recent_hashes:
                try:
                    distance = _hamming_distance(image_hash, existing_hash)
                    if distance < self._image_hash_threshold:
                        logger.debug(
                            f"Duplicate: image_hash distance={distance} "
                            f"(threshold={self._image_hash_threshold})"
                        )
                        return True
                except ValueError:
                    continue

        return False

    def cleanup_old(self) -> int:
        """Remove deals older than the dedup window. Returns count deleted."""
        cutoff = self._cutoff()
        result = self._session.execute(
            delete(Deal).where(Deal.created_at < cutoff)
        )
        self._session.commit()
        count = result.rowcount
        if count:
            logger.info(f"Cleaned up {count} old deals")
        return count
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_dedup.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add bot/dedup.py tests/test_dedup.py
git commit -m "feat: 3-layer duplicate checker with product ID, text hash, image hash"
```

---

### Task 7: AI Rewriter

**Files:**
- Create: `bot/rewriter.py`
- Create: `tests/test_rewriter.py`

- [ ] **Step 1: Write failing tests for rewriter**

File: `tests/test_rewriter.py`

```python
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.rewriter import ContentRewriter, RewriteResult


@pytest.fixture
def rewriter():
    return ContentRewriter(api_key="sk-test", model="gpt-4o-mini")


@pytest.mark.asyncio
class TestContentRewriter:
    async def test_rewrite_returns_structured_result(self, rewriter: ContentRewriter):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {
                            "rewritten_text": "🎧 אוזניות בלוטוס מטורפות!\n💰 רק 45 ש\"ח\n🚚 משלוח חינם",
                            "category": "tech",
                            "product_name_clean": "wireless bluetooth earbuds",
                        }
                    )
                )
            )
        ]

        with patch.object(
            rewriter._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await rewriter.rewrite(
                product_name="Wireless Earbuds",
                price=45.0,
                currency="ILS",
                shipping="חינם",
                original_text="Original deal text here",
            )

        assert isinstance(result, RewriteResult)
        assert "אוזניות" in result.rewritten_text
        assert result.category == "tech"
        assert result.product_name_clean == "wireless bluetooth earbuds"

    async def test_rewrite_handles_api_error_with_fallback(self, rewriter: ContentRewriter):
        with patch.object(
            rewriter._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=Exception("API error"),
        ):
            result = await rewriter.rewrite(
                product_name="Test Product",
                price=30.0,
                currency="ILS",
                original_text="Original text for fallback",
            )

        assert result is not None
        assert result.category == "other"
        assert "Test Product" in result.rewritten_text

    async def test_rewrite_handles_invalid_json(self, rewriter: ContentRewriter):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="not valid json"))
        ]

        with patch.object(
            rewriter._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await rewriter.rewrite(
                product_name="Test",
                price=10.0,
                currency="ILS",
                original_text="Original",
            )

        assert result is not None
        assert result.category == "other"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_rewriter.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'bot.rewriter'`

- [ ] **Step 3: Implement bot/rewriter.py**

```python
"""AI-powered content rewriting and categorization using OpenAI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from openai import AsyncOpenAI
from loguru import logger

_SYSTEM_PROMPT = """אתה כותב תוכן לערוץ דילים בטלגרם. אתה מקבל מידע על דיל ומחזיר JSON.

כללים לשכתוב:
- שנה את הניסוח לגמרי (אסור להעתיק מהמקור)
- שמור על כל המידע החשוב: מוצר, מחיר, משלוח
- הוסף אימוג'ים מתאימים
- הוסף 2-3 נקודות חיוביות על המוצר
- סגנון מושך ומזמין לרכישה
- אורך: 3-6 שורות
- כתוב בעברית בלבד

לקיטלוג, בחר קטגוריה אחת מ:
tech, home, fashion, beauty, toys, sports, auto, other

החזר JSON בלבד:
{"rewritten_text": "...", "category": "...", "product_name_clean": "שם מוצר נקי באנגלית"}"""


@dataclass(frozen=True)
class RewriteResult:
    rewritten_text: str
    category: str
    product_name_clean: str


class ContentRewriter:
    def __init__(self, api_key: str, model: str):
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def rewrite(
        self,
        product_name: str,
        price: Optional[float],
        currency: Optional[str],
        original_text: str,
        shipping: Optional[str] = None,
        rating: Optional[float] = None,
        sales_count: Optional[int] = None,
    ) -> RewriteResult:
        user_prompt = self._build_user_prompt(
            product_name, price, currency, shipping, rating, sales_count, original_text
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.8,
                max_tokens=500,
            )

            raw = response.choices[0].message.content
            data = json.loads(raw)

            return RewriteResult(
                rewritten_text=data["rewritten_text"],
                category=data.get("category", "other"),
                product_name_clean=data.get("product_name_clean", product_name),
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse AI response: {e}")
            return self._fallback(product_name, price, currency)
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return self._fallback(product_name, price, currency)

    def _build_user_prompt(
        self,
        product_name: str,
        price: Optional[float],
        currency: Optional[str],
        shipping: Optional[str],
        rating: Optional[float],
        sales_count: Optional[int],
        original_text: str,
    ) -> str:
        parts = [f"מוצר: {product_name}"]
        if price and currency:
            symbol = "₪" if currency == "ILS" else "$"
            parts.append(f"מחיר: {symbol}{price}")
        if shipping:
            parts.append(f"משלוח: {shipping}")
        if rating:
            parts.append(f"דירוג: {rating}")
        if sales_count:
            parts.append(f"מכירות: {sales_count}")
        parts.append(f"\nטקסט מקורי:\n{original_text}")
        return "\n".join(parts)

    def _fallback(
        self,
        product_name: str,
        price: Optional[float],
        currency: Optional[str],
    ) -> RewriteResult:
        """Template-based fallback when AI fails."""
        price_str = ""
        if price and currency:
            symbol = "₪" if currency == "ILS" else "$"
            price_str = f"\n💰 מחיר: {symbol}{price}"

        text = f"🔥 {product_name}{price_str}\n👉 לפרטים נוספים לחצו על הלינק"
        return RewriteResult(
            rewritten_text=text,
            category="other",
            product_name_clean=product_name,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_rewriter.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add bot/rewriter.py tests/test_rewriter.py
git commit -m "feat: AI content rewriter with OpenAI + template fallback"
```

---

### Task 8: Image Processor

**Files:**
- Create: `bot/image_processor.py`
- Create: `tests/test_image_processor.py`

- [ ] **Step 1: Write failing tests for image processor**

File: `tests/test_image_processor.py`

```python
import io
import pytest
from PIL import Image

from bot.image_processor import ImageProcessor, compute_image_hash


@pytest.fixture
def logo_bytes() -> bytes:
    """Create a small test logo (red square with transparency)."""
    logo = Image.new("RGBA", (100, 100), (255, 0, 0, 200))
    buf = io.BytesIO()
    logo.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_image_bytes() -> bytes:
    """Create a sample product image (blue rectangle)."""
    img = Image.new("RGB", (800, 600), (0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def processor(tmp_path, logo_bytes) -> ImageProcessor:
    logo_path = tmp_path / "logo.png"
    logo_path.write_bytes(logo_bytes)
    return ImageProcessor(
        logo_path=str(logo_path),
        position="bottom-right",
        opacity=0.4,
        scale=0.15,
    )


class TestWatermark:
    def test_add_watermark_returns_valid_image(
        self, processor: ImageProcessor, sample_image_bytes: bytes
    ):
        result = processor.add_watermark(sample_image_bytes)
        assert result is not None
        img = Image.open(io.BytesIO(result))
        assert img.size == (800, 600)

    def test_watermark_changes_image(
        self, processor: ImageProcessor, sample_image_bytes: bytes
    ):
        result = processor.add_watermark(sample_image_bytes)
        assert result != sample_image_bytes

    def test_watermark_bottom_right_position(
        self, processor: ImageProcessor, sample_image_bytes: bytes
    ):
        result = processor.add_watermark(sample_image_bytes)
        img = Image.open(io.BytesIO(result))
        # Bottom-right corner should no longer be pure blue
        pixel = img.getpixel((790, 590))
        assert pixel != (0, 0, 255), "Watermark should modify bottom-right area"

    def test_output_is_jpeg(self, processor: ImageProcessor, sample_image_bytes: bytes):
        result = processor.add_watermark(sample_image_bytes)
        img = Image.open(io.BytesIO(result))
        assert img.format == "JPEG"

    def test_large_image_gets_resized(self, processor: ImageProcessor):
        """Images over 10MB should be resized."""
        big_img = Image.new("RGB", (10000, 10000), (0, 255, 0))
        buf = io.BytesIO()
        big_img.save(buf, format="JPEG", quality=95)
        big_bytes = buf.getvalue()

        result = processor.add_watermark(big_bytes)
        result_img = Image.open(io.BytesIO(result))
        assert result_img.width <= 4096
        assert len(result) < 10_000_000


class TestImageHash:
    def test_same_image_same_hash(self, sample_image_bytes: bytes):
        hash1 = compute_image_hash(sample_image_bytes)
        hash2 = compute_image_hash(sample_image_bytes)
        assert hash1 == hash2

    def test_different_images_different_hash(self, sample_image_bytes: bytes):
        other = Image.new("RGB", (800, 600), (255, 0, 0))
        buf = io.BytesIO()
        other.save(buf, format="JPEG")

        hash1 = compute_image_hash(sample_image_bytes)
        hash2 = compute_image_hash(buf.getvalue())
        assert hash1 != hash2

    def test_hash_is_hex_string(self, sample_image_bytes: bytes):
        h = compute_image_hash(sample_image_bytes)
        assert isinstance(h, str)
        int(h, 16)  # Should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_image_processor.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'bot.image_processor'`

- [ ] **Step 3: Implement bot/image_processor.py**

```python
"""Image processing: watermark overlay and perceptual hashing."""

from __future__ import annotations

import io
from typing import Optional

import imagehash
from PIL import Image
from loguru import logger

_MAX_DIMENSION = 4096
_MAX_FILE_SIZE = 10_000_000  # 10MB Telegram limit


def compute_image_hash(image_bytes: bytes) -> str:
    """Compute perceptual hash (dhash) for duplicate detection."""
    img = Image.open(io.BytesIO(image_bytes))
    return str(imagehash.dhash(img))


class ImageProcessor:
    def __init__(
        self,
        logo_path: str,
        position: str = "bottom-right",
        opacity: float = 0.4,
        scale: float = 0.15,
    ):
        self._logo = Image.open(logo_path).convert("RGBA")
        self._position = position
        self._opacity = opacity
        self._scale = scale

    def add_watermark(self, image_bytes: bytes) -> bytes:
        """Add watermark logo to image. Returns JPEG bytes."""
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Resize if too large
        img = self._resize_if_needed(img)

        # Prepare logo for this image size
        logo = self._prepare_logo(img.width, img.height)

        # Compute position
        x, y = self._compute_position(img.width, img.height, logo.width, logo.height)

        # Paste with transparency
        img.paste(logo, (x, y), logo)

        # Encode as JPEG
        buf = io.BytesIO()
        quality = 90
        img.save(buf, format="JPEG", quality=quality)

        # Reduce quality if still too large
        while buf.tell() > _MAX_FILE_SIZE and quality > 30:
            quality -= 10
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality)

        return buf.getvalue()

    def _prepare_logo(self, img_width: int, img_height: int) -> Image.Image:
        logo_width = int(img_width * self._scale)
        logo_height = int(self._logo.height * (logo_width / self._logo.width))
        logo = self._logo.resize((logo_width, logo_height), Image.LANCZOS)

        # Apply opacity
        r, g, b, a = logo.split()
        a = a.point(lambda p: int(p * self._opacity))
        logo.putalpha(a)

        return logo

    def _compute_position(
        self, img_w: int, img_h: int, logo_w: int, logo_h: int
    ) -> tuple[int, int]:
        margin = 10
        positions = {
            "bottom-right": (img_w - logo_w - margin, img_h - logo_h - margin),
            "bottom-left": (margin, img_h - logo_h - margin),
            "top-right": (img_w - logo_w - margin, margin),
            "top-left": (margin, margin),
        }
        return positions.get(self._position, positions["bottom-right"])

    def _resize_if_needed(self, img: Image.Image) -> Image.Image:
        if img.width <= _MAX_DIMENSION and img.height <= _MAX_DIMENSION:
            return img

        ratio = min(_MAX_DIMENSION / img.width, _MAX_DIMENSION / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        logger.info(f"Resizing image from {img.size} to {new_size}")
        return img.resize(new_size, Image.LANCZOS)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_image_processor.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add bot/image_processor.py tests/test_image_processor.py
git commit -m "feat: image processor with watermark overlay and perceptual hashing"
```

---

### Task 9: Processing Pipeline

**Files:**
- Create: `bot/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests for pipeline**

File: `tests/test_pipeline.py`

```python
import datetime
import json
import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image
from sqlalchemy import select

from bot.pipeline import Pipeline
from bot.models import RawMessage, Deal, PublishQueueItem
from bot.parser import DealParser
from bot.dedup import DuplicateChecker
from bot.resolver import LinkResolver
from bot.rewriter import ContentRewriter, RewriteResult
from bot.image_processor import ImageProcessor


def _make_test_image() -> bytes:
    img = Image.new("RGB", (200, 200), (0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def pipeline_deps(db_session, tmp_path):
    """Create pipeline with mocked external deps."""
    parser = DealParser(min_message_length=20, supported_domains=["aliexpress.com", "s.click.aliexpress.com"])

    dedup = DuplicateChecker(session=db_session, window_hours=24, image_hash_threshold=5)

    resolver = LinkResolver()
    resolver.resolve = AsyncMock(return_value="1005003091506814")

    rewriter = ContentRewriter(api_key="test", model="test")
    rewriter.rewrite = AsyncMock(
        return_value=RewriteResult(
            rewritten_text="🔥 מוצר מעולה!",
            category="tech",
            product_name_clean="test product",
        )
    )

    # Create logo for image processor
    logo_path = tmp_path / "logo.png"
    logo = Image.new("RGBA", (50, 50), (255, 0, 0, 200))
    logo.save(str(logo_path), "PNG")
    image_proc = ImageProcessor(logo_path=str(logo_path))

    target_groups = {"default": "@my_channel"}
    notifier = MagicMock()
    notifier.notify_error = AsyncMock()

    return {
        "parser": parser,
        "dedup": dedup,
        "resolver": resolver,
        "rewriter": rewriter,
        "image_processor": image_proc,
        "session": db_session,
        "target_groups": target_groups,
        "notifier": notifier,
    }


@pytest.fixture
def pipeline(pipeline_deps) -> Pipeline:
    return Pipeline(**pipeline_deps)


@pytest.mark.asyncio
class TestPipeline:
    async def test_full_pipeline_creates_deal_and_queue_item(
        self, pipeline: Pipeline, db_session
    ):
        text = "Amazing earbuds! https://s.click.aliexpress.com/e/_abc123 only ₪45 free shipping"
        images = [_make_test_image()]

        await pipeline.process(
            text=text,
            images=images,
            source_group="@deals_il",
            telegram_message_id=12345,
        )

        # Should create a raw message
        raw = db_session.execute(select(RawMessage)).scalar_one()
        assert raw.status == "processed"

        # Should create a deal
        deal = db_session.execute(select(Deal)).scalar_one()
        assert deal.rewritten_text == "🔥 מוצר מעולה!"
        assert deal.category == "tech"
        assert deal.price == 45.0

        # Should enqueue for publishing
        queue = db_session.execute(select(PublishQueueItem)).scalar_one()
        assert queue.status == "queued"
        assert queue.target_group == "@my_channel"

    async def test_duplicate_deal_skips_publishing(
        self, pipeline: Pipeline, db_session
    ):
        text = "Deal! https://s.click.aliexpress.com/e/_abc ₪45 great product"
        images = [_make_test_image()]

        # Process first time
        await pipeline.process(text=text, images=images, source_group="@g1", telegram_message_id=1)
        # Process same deal again
        await pipeline.process(text=text, images=images, source_group="@g2", telegram_message_id=2)

        # Should have 2 raw messages
        raws = db_session.execute(select(RawMessage)).scalars().all()
        assert len(raws) == 2

        # But only 1 deal and 1 queue item
        deals = db_session.execute(select(Deal)).scalars().all()
        assert len(deals) == 1

    async def test_no_link_message_skips(self, pipeline: Pipeline, db_session):
        text = "This is a general message without any deal link at all"

        await pipeline.process(text=text, images=[], source_group="@g1", telegram_message_id=3)

        raw = db_session.execute(select(RawMessage)).scalar_one()
        assert raw.status == "processed"

        deals = db_session.execute(select(Deal)).scalars().all()
        assert len(deals) == 0

    async def test_resolver_failure_continues_without_product_id(
        self, pipeline: Pipeline, pipeline_deps, db_session
    ):
        pipeline_deps["resolver"].resolve = AsyncMock(return_value=None)

        text = "Good deal https://s.click.aliexpress.com/e/_fail ₪30 cheap"

        await pipeline.process(text=text, images=[], source_group="@g1", telegram_message_id=4)

        deal = db_session.execute(select(Deal)).scalar_one()
        assert deal.product_id is None
        assert deal.price == 30.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_pipeline.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'bot.pipeline'`

- [ ] **Step 3: Implement bot/pipeline.py**

```python
"""Processing pipeline: orchestrates all deal processing stages."""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session
from loguru import logger

from bot.parser import DealParser, ParsedDeal
from bot.dedup import DuplicateChecker
from bot.resolver import LinkResolver
from bot.rewriter import ContentRewriter
from bot.image_processor import ImageProcessor, compute_image_hash
from bot.models import RawMessage, Deal, PublishQueueItem, DailyStat


class Pipeline:
    def __init__(
        self,
        parser: DealParser,
        dedup: DuplicateChecker,
        resolver: LinkResolver,
        rewriter: ContentRewriter,
        image_processor: ImageProcessor,
        session: Session,
        target_groups: dict[str, str],
        notifier: object,
    ):
        self._parser = parser
        self._dedup = dedup
        self._resolver = resolver
        self._rewriter = rewriter
        self._image_processor = image_processor
        self._session = session
        self._target_groups = target_groups
        self._notifier = notifier

    async def process(
        self,
        text: str,
        images: list[bytes],
        source_group: str,
        telegram_message_id: int,
    ) -> Optional[Deal]:
        # Step 0: Save raw message
        raw = RawMessage(
            source_group=source_group,
            telegram_message_id=telegram_message_id,
            raw_text=text,
            has_images=len(images) > 0,
            received_at=datetime.datetime.now(datetime.UTC),
            status="pending",
        )
        self._session.add(raw)
        self._session.flush()

        self._increment_stat("deals_seen")

        try:
            deal = await self._process_stages(raw, text, images, source_group)
            raw.status = "processed"
            self._session.commit()
            return deal
        except Exception as e:
            raw.status = "failed"
            raw.error_message = str(e)[:500]
            self._session.commit()
            self._increment_stat("deals_skipped_error")
            logger.error(f"Pipeline error for message {telegram_message_id}: {e}")
            if hasattr(self._notifier, "notify_error"):
                await self._notifier.notify_error(f"Pipeline error: {e}")
            return None

    async def _process_stages(
        self,
        raw: RawMessage,
        text: str,
        images: list[bytes],
        source_group: str,
    ) -> Optional[Deal]:
        # Step 1: Parse
        parsed = self._parser.parse(text)
        if parsed is None:
            logger.debug(f"No AliExpress link found, skipping")
            return None

        # Step 2: Resolve link → product ID
        product_id = parsed.product_id
        if product_id is None:
            product_id = await self._resolver.resolve(parsed.link)

        # Step 3: Compute hashes
        text_hash = hashlib.md5(
            (parsed.raw_text or "").lower().strip().encode()
        ).hexdigest()

        image_hash = None
        if images:
            try:
                image_hash = compute_image_hash(images[0])
            except Exception as e:
                logger.warning(f"Image hash failed: {e}")

        # Step 4: Dedup check
        if self._dedup.is_duplicate(
            product_id=product_id,
            text_hash=text_hash,
            image_hash=image_hash,
        ):
            logger.info(f"Duplicate deal detected, skipping")
            self._increment_stat("deals_skipped_dup")
            return None

        # Step 5: AI rewrite + categorize
        rewrite_result = await self._rewriter.rewrite(
            product_name=parsed.raw_text[:100],
            price=parsed.price,
            currency=parsed.currency,
            shipping=parsed.shipping,
            original_text=text,
        )

        # Step 6: Process images (watermark)
        processed_images: list[bytes] = []
        for img_bytes in images:
            try:
                processed = self._image_processor.add_watermark(img_bytes)
                processed_images.append(processed)
            except Exception as e:
                logger.warning(f"Watermark failed, using original: {e}")
                processed_images.append(img_bytes)

        # Step 7: Save deal to DB
        deal = Deal(
            raw_message_id=raw.id,
            product_id=product_id,
            product_name=rewrite_result.product_name_clean,
            original_text=text,
            rewritten_text=rewrite_result.rewritten_text,
            price=parsed.price or 0.0,
            original_price=parsed.original_price,
            currency=parsed.currency or "ILS",
            shipping=parsed.shipping,
            category=rewrite_result.category,
            product_link=parsed.link,
            image_hash=image_hash,
            text_hash=text_hash,
            source_group=source_group,
            created_at=datetime.datetime.now(datetime.UTC),
        )
        self._session.add(deal)
        self._session.flush()

        # Save processed image to disk for publisher
        if processed_images:
            image_dir = Path("data/images")
            image_dir.mkdir(parents=True, exist_ok=True)
            img_path = image_dir / f"{deal.id}.jpg"
            img_path.write_bytes(processed_images[0])
            deal.image_path = str(img_path)

        # Step 8: Enqueue for publishing
        target = self._target_groups.get(rewrite_result.category)
        if target is None:
            target = self._target_groups.get("default", "")

        queue_item = PublishQueueItem(
            deal_id=deal.id,
            target_group=target,
            status="queued",
            scheduled_after=datetime.datetime.now(datetime.UTC),
        )
        self._session.add(queue_item)
        self._session.commit()

        self._increment_stat("deals_processed")
        logger.info(
            f"Deal processed: {rewrite_result.product_name_clean} "
            f"→ {rewrite_result.category} → queued"
        )

        return deal

    def _increment_stat(self, field: str) -> None:
        today = datetime.date.today()
        stat = self._session.query(DailyStat).filter_by(date=today).first()
        if stat is None:
            stat = DailyStat(date=today)
            self._session.add(stat)
        setattr(stat, field, getattr(stat, field) + 1)
        self._session.flush()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_pipeline.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add bot/pipeline.py tests/test_pipeline.py
git commit -m "feat: processing pipeline orchestrating parse, dedup, resolve, rewrite, image, enqueue"
```

---

### Task 10: Queue-Based Publisher

**Files:**
- Create: `bot/publisher.py`
- Create: `tests/test_publisher.py`

- [ ] **Step 1: Write failing tests for publisher queue logic**

File: `tests/test_publisher.py`

```python
import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select

from bot.publisher import DealPublisher
from bot.models import Deal, PublishQueueItem, RawMessage, DailyStat


def _seed_deal(db_session, deal_id: int = 1) -> tuple[Deal, PublishQueueItem]:
    raw = RawMessage(
        source_group="@test",
        telegram_message_id=deal_id,
        raw_text="text",
        has_images=False,
        received_at=datetime.datetime.now(datetime.UTC),
        status="processed",
    )
    db_session.add(raw)
    db_session.flush()

    deal = Deal(
        raw_message_id=raw.id,
        product_name="Test Product",
        original_text="orig",
        rewritten_text="🔥 Test deal ₪45",
        price=45.0,
        currency="ILS",
        category="tech",
        product_link="https://aliexpress.com/item/123.html",
        text_hash=f"hash_{deal_id}",
        source_group="@test",
        created_at=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(deal)
    db_session.flush()

    queue_item = PublishQueueItem(
        deal_id=deal.id,
        target_group="@my_channel",
        status="queued",
        scheduled_after=datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=1),
    )
    db_session.add(queue_item)
    db_session.commit()
    return deal, queue_item


@pytest.fixture
def publisher(db_session):
    return DealPublisher(
        send_func=AsyncMock(return_value=99999),
        session=db_session,
        min_delay=300,
        max_delay=600,
        max_posts_per_hour=4,
        quiet_hours_start=23,
        quiet_hours_end=7,
    )


class TestQueuePicking:
    def test_picks_oldest_queued_item(self, publisher: DealPublisher, db_session):
        _seed_deal(db_session, deal_id=1)
        _seed_deal(db_session, deal_id=2)

        item = publisher.pick_next()
        assert item is not None
        assert item.status == "queued"

    def test_skips_already_published(self, publisher: DealPublisher, db_session):
        _, qi = _seed_deal(db_session, deal_id=1)
        qi.status = "published"
        db_session.commit()

        item = publisher.pick_next()
        assert item is None

    def test_respects_scheduled_after(self, publisher: DealPublisher, db_session):
        _, qi = _seed_deal(db_session, deal_id=1)
        qi.scheduled_after = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)
        db_session.commit()

        item = publisher.pick_next()
        assert item is None

    def test_returns_none_when_empty(self, publisher: DealPublisher):
        item = publisher.pick_next()
        assert item is None


class TestQuietHours:
    def test_is_quiet_at_midnight(self, publisher: DealPublisher):
        midnight = datetime.datetime(2026, 1, 1, 0, 0)
        assert publisher.is_quiet_hour(midnight) is True

    def test_is_not_quiet_at_noon(self, publisher: DealPublisher):
        noon = datetime.datetime(2026, 1, 1, 12, 0)
        assert publisher.is_quiet_hour(noon) is False

    def test_is_quiet_at_23(self, publisher: DealPublisher):
        late = datetime.datetime(2026, 1, 1, 23, 30)
        assert publisher.is_quiet_hour(late) is True

    def test_is_not_quiet_at_7(self, publisher: DealPublisher):
        morning = datetime.datetime(2026, 1, 1, 7, 0)
        assert publisher.is_quiet_hour(morning) is False


class TestRateLimit:
    def test_rate_limit_blocks_after_max(self, publisher: DealPublisher, db_session):
        for i in range(4):
            _, qi = _seed_deal(db_session, deal_id=100 + i)
            qi.status = "published"
            qi.published_at = datetime.datetime.now(datetime.UTC)
            db_session.commit()

        assert publisher.is_rate_limited("@my_channel") is True

    def test_rate_limit_allows_under_max(self, publisher: DealPublisher, db_session):
        assert publisher.is_rate_limited("@my_channel") is False


@pytest.mark.asyncio
class TestPublishExecution:
    async def test_publish_marks_as_published(self, publisher: DealPublisher, db_session):
        deal, qi = _seed_deal(db_session, deal_id=1)

        await publisher.publish_one(qi, deal)

        db_session.refresh(qi)
        assert qi.status == "published"
        assert qi.message_id == 99999
        assert qi.published_at is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_publisher.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'bot.publisher'`

- [ ] **Step 3: Implement bot/publisher.py**

```python
"""Queue-based deal publisher with rate limiting and quiet hours."""

from __future__ import annotations

import datetime
import random
from typing import Callable, Awaitable, Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session
from loguru import logger

from bot.models import Deal, PublishQueueItem, DailyStat


class DealPublisher:
    def __init__(
        self,
        send_func: Callable[..., Awaitable[int]],
        session: Session,
        min_delay: int,
        max_delay: int,
        max_posts_per_hour: int,
        quiet_hours_start: int,
        quiet_hours_end: int,
    ):
        self._send = send_func
        self._session = session
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._max_posts_per_hour = max_posts_per_hour
        self._quiet_start = quiet_hours_start
        self._quiet_end = quiet_hours_end
        self.paused = False

    def pick_next(self) -> Optional[PublishQueueItem]:
        """Get the oldest queued item ready to publish."""
        now = datetime.datetime.now(datetime.UTC)
        return self._session.execute(
            select(PublishQueueItem)
            .where(
                PublishQueueItem.status == "queued",
                PublishQueueItem.scheduled_after <= now,
            )
            .order_by(
                PublishQueueItem.priority.desc(),
                PublishQueueItem.scheduled_after.asc(),
            )
            .limit(1)
        ).scalar_one_or_none()

    def is_quiet_hour(self, now: Optional[datetime.datetime] = None) -> bool:
        if now is None:
            now = datetime.datetime.now()
        hour = now.hour
        if self._quiet_start > self._quiet_end:
            return hour >= self._quiet_start or hour < self._quiet_end
        return self._quiet_start <= hour < self._quiet_end

    def is_rate_limited(self, target_group: str) -> bool:
        one_hour_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
        count = self._session.execute(
            select(func.count())
            .select_from(PublishQueueItem)
            .where(
                PublishQueueItem.target_group == target_group,
                PublishQueueItem.status == "published",
                PublishQueueItem.published_at >= one_hour_ago,
            )
        ).scalar()
        return (count or 0) >= self._max_posts_per_hour

    async def publish_one(self, queue_item: PublishQueueItem, deal: Deal) -> None:
        """Publish a single deal and update its status."""
        queue_item.status = "publishing"
        self._session.flush()

        try:
            message_id = await self._send(
                target_group=queue_item.target_group,
                text=deal.rewritten_text,
                link=deal.affiliate_link or deal.product_link,
                image_path=deal.image_path,
            )

            queue_item.status = "published"
            queue_item.published_at = datetime.datetime.now(datetime.UTC)
            queue_item.message_id = message_id
            self._session.commit()

            self._increment_stat("deals_published")
            logger.info(f"Published deal {deal.id} to {queue_item.target_group}")

        except Exception as e:
            queue_item.status = "failed"
            queue_item.error_message = str(e)[:500]
            self._session.commit()
            logger.error(f"Failed to publish deal {deal.id}: {e}")
            raise

    async def check_queue(self) -> None:
        """Called by scheduler: pick next deal and publish if conditions allow."""
        if self.paused:
            return

        if self.is_quiet_hour():
            return

        item = self.pick_next()
        if item is None:
            return

        if self.is_rate_limited(item.target_group):
            logger.debug(f"Rate limited for {item.target_group}, skipping cycle")
            return

        deal = self._session.get(Deal, item.deal_id)
        if deal is None:
            item.status = "failed"
            item.error_message = "Deal not found"
            self._session.commit()
            return

        await self.publish_one(item, deal)

    def get_random_delay(self) -> int:
        return random.randint(self._min_delay, self._max_delay)

    def _increment_stat(self, field: str) -> None:
        today = datetime.date.today()
        stat = self._session.query(DailyStat).filter_by(date=today).first()
        if stat is None:
            stat = DailyStat(date=today)
            self._session.add(stat)
        setattr(stat, field, getattr(stat, field) + 1)
        self._session.flush()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_publisher.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add bot/publisher.py tests/test_publisher.py
git commit -m "feat: queue-based publisher with rate limiting and quiet hours"
```

---

### Task 11: Notifier

**Files:**
- Create: `bot/notifier.py`

- [ ] **Step 1: Implement bot/notifier.py**

No TDD here — this component's only job is sending Telegram messages, which requires a live client to test meaningfully. We test it indirectly through the pipeline integration tests.

```python
"""Send error alerts and daily summaries to admin via Telegram."""

from __future__ import annotations

import datetime

from sqlalchemy.orm import Session
from loguru import logger

from bot.models import DailyStat


class Notifier:
    def __init__(self, send_message_func, session: Session):
        self._send = send_message_func
        self._session = session

    async def notify_error(self, message: str) -> None:
        """Send critical error alert to admin."""
        text = f"⚠️ שגיאה בבוט:\n{message[:1000]}"
        try:
            await self._send(text)
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")

    async def send_daily_summary(self) -> None:
        """Send daily statistics summary to admin."""
        today = datetime.date.today()
        stat = self._session.query(DailyStat).filter_by(date=today).first()

        if stat is None:
            text = "📊 סיכום יומי:\nלא היתה פעילות היום."
        else:
            text = (
                f"📊 סיכום יומי — {today.isoformat()}\n\n"
                f"👀 דילים שנראו: {stat.deals_seen}\n"
                f"✅ עובדו: {stat.deals_processed}\n"
                f"📤 פורסמו: {stat.deals_published}\n"
                f"🔁 כפילויות: {stat.deals_skipped_dup}\n"
                f"❌ שגיאות: {stat.deals_skipped_error}\n"
                f"🔌 קריאות API: {stat.api_calls}"
            )

        try:
            await self._send(text)
            logger.info("Daily summary sent")
        except Exception as e:
            logger.error(f"Failed to send daily summary: {e}")

    async def notify_startup(self) -> None:
        await self._send("🟢 הבוט עלה לאוויר!")

    async def notify_shutdown(self) -> None:
        await self._send("🔴 הבוט נכבה.")
```

- [ ] **Step 2: Commit**

```bash
git add bot/notifier.py
git commit -m "feat: notifier for error alerts and daily summaries"
```

---

### Task 12: Telegram Admin Commands

**Files:**
- Create: `bot/admin.py`

- [ ] **Step 1: Implement bot/admin.py**

Admin commands depend on Telethon client — tested via manual integration testing.

```python
"""Telegram admin commands for bot control."""

from __future__ import annotations

import datetime

from sqlalchemy import select, func
from sqlalchemy.orm import Session
from loguru import logger

from bot.models import Deal, PublishQueueItem, DailyStat


class AdminCommands:
    def __init__(
        self,
        session: Session,
        admin_user_id: int,
        publisher,
    ):
        self._session = session
        self._admin_user_id = admin_user_id
        self._publisher = publisher

    def is_admin(self, user_id: int) -> bool:
        return user_id == self._admin_user_id

    async def handle_command(self, user_id: int, text: str) -> str | None:
        """Parse and execute admin command. Returns response text or None."""
        if not self.is_admin(user_id):
            return None

        text = text.strip()
        if text == "/stats":
            return self._cmd_stats()
        elif text == "/pause":
            return self._cmd_pause()
        elif text == "/resume":
            return self._cmd_resume()
        elif text == "/queue":
            return self._cmd_queue()
        elif text.startswith("/skip"):
            return self._cmd_skip(text)
        elif text == "/last":
            return self._cmd_last()

        return None

    def _cmd_stats(self) -> str:
        today = datetime.date.today()
        stat = self._session.query(DailyStat).filter_by(date=today).first()
        if stat is None:
            return "📊 אין סטטיסטיקות להיום."
        return (
            f"📊 סטטיסטיקות — {today.isoformat()}\n\n"
            f"👀 נראו: {stat.deals_seen}\n"
            f"✅ עובדו: {stat.deals_processed}\n"
            f"📤 פורסמו: {stat.deals_published}\n"
            f"🔁 כפילויות: {stat.deals_skipped_dup}\n"
            f"❌ שגיאות: {stat.deals_skipped_error}"
        )

    def _cmd_pause(self) -> str:
        self._publisher.paused = True
        logger.info("Publishing paused by admin")
        return "⏸ פרסום הופסק. העיבוד ממשיך."

    def _cmd_resume(self) -> str:
        self._publisher.paused = False
        logger.info("Publishing resumed by admin")
        return "▶️ פרסום חודש."

    def _cmd_queue(self) -> str:
        count = self._session.execute(
            select(func.count())
            .select_from(PublishQueueItem)
            .where(PublishQueueItem.status == "queued")
        ).scalar()
        return f"📋 {count} דילים בתור לפרסום."

    def _cmd_skip(self, text: str) -> str:
        parts = text.split()
        if len(parts) < 2:
            return "Usage: /skip <deal_id>"
        try:
            deal_id = int(parts[1])
        except ValueError:
            return "Usage: /skip <deal_id> (מספר)"

        item = self._session.execute(
            select(PublishQueueItem).where(
                PublishQueueItem.deal_id == deal_id,
                PublishQueueItem.status == "queued",
            )
        ).scalar_one_or_none()

        if item is None:
            return f"לא נמצא דיל {deal_id} בתור."

        item.status = "failed"
        item.error_message = "Skipped by admin"
        self._session.commit()
        return f"⏭ דיל {deal_id} דולג."

    def _cmd_last(self) -> str:
        items = self._session.execute(
            select(PublishQueueItem, Deal)
            .join(Deal, PublishQueueItem.deal_id == Deal.id)
            .where(PublishQueueItem.status == "published")
            .order_by(PublishQueueItem.published_at.desc())
            .limit(5)
        ).all()

        if not items:
            return "אין פרסומים אחרונים."

        lines = ["📤 5 אחרונים:\n"]
        for qi, deal in items:
            time_str = qi.published_at.strftime("%H:%M") if qi.published_at else "?"
            lines.append(f"• [{time_str}] {deal.product_name[:40]} — ₪{deal.price}")

        return "\n".join(lines)
```

- [ ] **Step 2: Commit**

```bash
git add bot/admin.py
git commit -m "feat: Telegram admin commands (stats, pause, resume, queue, skip, last)"
```

---

### Task 13: Telegram Listener

**Files:**
- Create: `bot/listener.py`

- [ ] **Step 1: Implement bot/listener.py**

```python
"""Telegram listener: captures new messages from source deal groups."""

from __future__ import annotations

import io
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto
from loguru import logger

from bot.pipeline import Pipeline
from bot.admin import AdminCommands


class TelegramListener:
    def __init__(
        self,
        client: TelegramClient,
        source_groups: list[str],
        min_message_length: int,
        pipeline: Pipeline,
        admin: AdminCommands,
    ):
        self._client = client
        self._source_groups = source_groups
        self._min_length = min_message_length
        self._pipeline = pipeline
        self._admin = admin

    def register(self) -> None:
        """Register event handlers on the Telethon client."""

        @self._client.on(events.NewMessage(chats=self._source_groups))
        async def on_source_message(event):
            await self._handle_source_message(event)

        @self._client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def on_private_message(event):
            await self._handle_admin_message(event)

        logger.info(f"Registered listeners for {len(self._source_groups)} source groups")

    async def _handle_source_message(self, event) -> None:
        message = event.message
        text = message.text or ""

        if len(text) < self._min_length:
            return

        # Download images if present
        images: list[bytes] = []
        if isinstance(message.media, MessageMediaPhoto):
            try:
                img_bytes = await self._client.download_media(message, bytes)
                if img_bytes:
                    images.append(img_bytes)
            except Exception as e:
                logger.warning(f"Failed to download image: {e}")

        source_group = ""
        if hasattr(event.chat, "username") and event.chat.username:
            source_group = f"@{event.chat.username}"
        elif hasattr(event.chat, "title"):
            source_group = event.chat.title

        logger.debug(f"New message from {source_group}: {text[:80]}...")

        await self._pipeline.process(
            text=text,
            images=images,
            source_group=source_group,
            telegram_message_id=message.id,
        )

    async def _handle_admin_message(self, event) -> None:
        sender = await event.get_sender()
        if sender is None:
            return

        response = await self._admin.handle_command(sender.id, event.text or "")
        if response:
            await event.reply(response)
```

- [ ] **Step 2: Commit**

```bash
git add bot/listener.py
git commit -m "feat: Telegram listener for source groups and admin commands"
```

---

### Task 14: Main Entry Point & Integration

**Files:**
- Create: `main.py`

- [ ] **Step 1: Implement main.py**

```python
"""Entry point: wire all components and start the bot."""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv
from loguru import logger
from telethon import TelegramClient, Button
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from bot.config import load_config, AppConfig
from bot.models import init_db, Deal
from bot.parser import DealParser
from bot.dedup import DuplicateChecker
from bot.resolver import LinkResolver
from bot.rewriter import ContentRewriter
from bot.image_processor import ImageProcessor
from bot.pipeline import Pipeline
from bot.publisher import DealPublisher
from bot.notifier import Notifier
from bot.admin import AdminCommands
from bot.listener import TelegramListener


def _setup_logging():
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(
        "data/bot.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
    )


async def _send_telegram_message(client: TelegramClient, admin_chat: str, text: str):
    await client.send_message(admin_chat, text)


async def _send_deal(
    client: TelegramClient,
    target_group: str,
    text: str,
    link: str,
    image_path: str | None = None,
) -> int:
    """Send deal to target group. Returns message ID."""
    button = Button.url("🛒 לרכישה", link)
    caption = f"{text}\n\n👇 לרכישה לחצו למטה"

    if image_path:
        msg = await client.send_file(
            target_group,
            image_path,
            caption=caption,
            buttons=[button],
        )
    else:
        msg = await client.send_message(
            target_group,
            caption,
            buttons=[button],
        )
    return msg.id


async def main():
    load_dotenv()
    _setup_logging()
    logger.info("Starting AliExpress Deal Bot...")

    config = load_config("config.yaml")

    # Database
    SessionFactory = init_db("data/deals.db")
    session = SessionFactory()

    # Telethon client
    client = TelegramClient(
        "data/bot",
        config.telegram.api_id,
        config.telegram.api_hash,
    )
    await client.start(phone=config.telegram.phone)
    logger.info("Telegram client connected")

    # Notifier (needs client)
    async def send_to_admin(text: str):
        await _send_telegram_message(client, config.telegram.admin_chat, text)

    notifier = Notifier(send_message_func=send_to_admin, session=session)

    # Components
    parser = DealParser(
        min_message_length=config.parser.min_message_length,
        supported_domains=config.parser.supported_domains,
    )
    dedup = DuplicateChecker(
        session=session,
        window_hours=config.dedup.window_hours,
        image_hash_threshold=config.dedup.image_hash_threshold,
    )
    resolver = LinkResolver()
    rewriter = ContentRewriter(
        api_key=config.openai.api_key,
        model=config.openai.model,
    )
    image_processor = ImageProcessor(
        logo_path=config.watermark.logo_path,
        position=config.watermark.position,
        opacity=config.watermark.opacity,
        scale=config.watermark.scale,
    )

    # Pipeline
    pipeline = Pipeline(
        parser=parser,
        dedup=dedup,
        resolver=resolver,
        rewriter=rewriter,
        image_processor=image_processor,
        session=session,
        target_groups=config.telegram.target_groups,
        notifier=notifier,
    )

    # Publisher
    async def send_deal_wrapper(target_group: str, text: str, link: str, image_path=None) -> int:
        return await _send_deal(client, target_group, text, link, image_path)

    publisher = DealPublisher(
        send_func=send_deal_wrapper,
        session=session,
        min_delay=config.publishing.min_delay_seconds,
        max_delay=config.publishing.max_delay_seconds,
        max_posts_per_hour=config.publishing.max_posts_per_hour,
        quiet_hours_start=config.publishing.quiet_hours_start,
        quiet_hours_end=config.publishing.quiet_hours_end,
    )

    # Admin
    admin = AdminCommands(
        session=session,
        admin_user_id=config.telegram.admin_user_id,
        publisher=publisher,
    )

    # Listener
    listener = TelegramListener(
        client=client,
        source_groups=config.telegram.source_groups,
        min_message_length=config.parser.min_message_length,
        pipeline=pipeline,
        admin=admin,
    )
    listener.register()

    # Scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(publisher.check_queue, IntervalTrigger(minutes=3), id="publisher")
    scheduler.add_job(notifier.send_daily_summary, CronTrigger(hour=21, minute=0), id="daily_summary")
    scheduler.add_job(dedup.cleanup_old, CronTrigger(hour=3, minute=0), id="dedup_cleanup")
    scheduler.start()
    logger.info("Scheduler started")

    # Startup notification
    await notifier.notify_startup()

    # Run
    logger.info("Bot is running! Listening for deals...")
    try:
        await client.run_until_disconnected()
    finally:
        await notifier.notify_shutdown()
        scheduler.shutdown()
        session.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Verify the bot starts (requires .env with real credentials)**

```bash
# This requires real Telegram credentials - do a manual smoke test
python main.py
```

Expected: Bot connects to Telegram, prints "Bot is running!", listens for messages.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: main entry point wiring all components with scheduler"
```

---

### Task 15: Dashboard — Base Setup & Main Page

**Files:**
- Create: `dashboard/app.py`
- Create: `dashboard/routes.py`
- Create: `dashboard/templates/base.html`
- Create: `dashboard/templates/index.html`

- [ ] **Step 1: Implement dashboard/app.py**

```python
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

    # Store deps for route access
    app.state.session_factory = session_factory
    app.state.config = config
    app.state.templates = templates

    from dashboard.routes import register_routes
    register_routes(app)

    return app
```

- [ ] **Step 2: Implement dashboard/templates/base.html**

```html
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}AliBot Dashboard{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    {% if auto_refresh %}
    <meta http-equiv="refresh" content="{{ auto_refresh }}">
    {% endif %}
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
    </style>
</head>
<body class="bg-gray-50 text-gray-900">
    <nav class="bg-white shadow-sm border-b">
        <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
            <h1 class="text-xl font-bold">🤖 AliBot</h1>
            <div class="flex gap-4 text-sm">
                <a href="/" class="hover:text-blue-600">ראשי</a>
                <a href="/deals" class="hover:text-blue-600">דילים</a>
                <a href="/queue" class="hover:text-blue-600">תור</a>
                <a href="/settings" class="hover:text-blue-600">הגדרות</a>
                <a href="/logs" class="hover:text-blue-600">לוגים</a>
            </div>
        </div>
    </nav>
    <main class="max-w-7xl mx-auto px-4 py-6">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

- [ ] **Step 3: Implement dashboard/templates/index.html**

```html
{% extends "base.html" %}
{% block title %}AliBot — ראשי{% endblock %}
{% block content %}
<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
    <div class="bg-white rounded-lg shadow p-6">
        <div class="text-sm text-gray-500">דילים שנראו היום</div>
        <div class="text-3xl font-bold">{{ stats.deals_seen }}</div>
    </div>
    <div class="bg-white rounded-lg shadow p-6">
        <div class="text-sm text-gray-500">פורסמו היום</div>
        <div class="text-3xl font-bold text-green-600">{{ stats.deals_published }}</div>
    </div>
    <div class="bg-white rounded-lg shadow p-6">
        <div class="text-sm text-gray-500">בתור לפרסום</div>
        <div class="text-3xl font-bold text-blue-600">{{ queue_count }}</div>
    </div>
</div>

<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
    <div class="bg-white rounded-lg shadow p-6">
        <div class="text-sm text-gray-500">כפילויות שנדחו</div>
        <div class="text-2xl font-bold text-yellow-600">{{ stats.deals_skipped_dup }}</div>
    </div>
    <div class="bg-white rounded-lg shadow p-6">
        <div class="text-sm text-gray-500">שגיאות</div>
        <div class="text-2xl font-bold text-red-600">{{ stats.deals_skipped_error }}</div>
    </div>
</div>

<h2 class="text-lg font-semibold mb-4">דילים אחרונים</h2>
<div class="bg-white rounded-lg shadow overflow-hidden">
    <table class="w-full text-sm">
        <thead class="bg-gray-50">
            <tr>
                <th class="px-4 py-3 text-right">מוצר</th>
                <th class="px-4 py-3 text-right">מחיר</th>
                <th class="px-4 py-3 text-right">קטגוריה</th>
                <th class="px-4 py-3 text-right">סטטוס</th>
                <th class="px-4 py-3 text-right">זמן</th>
            </tr>
        </thead>
        <tbody class="divide-y">
            {% for deal, status in recent_deals %}
            <tr class="hover:bg-gray-50">
                <td class="px-4 py-3">
                    <a href="/deals/{{ deal.id }}" class="text-blue-600 hover:underline">
                        {{ deal.product_name[:50] }}
                    </a>
                </td>
                <td class="px-4 py-3">{{ "₪" if deal.currency == "ILS" else "$" }}{{ deal.price }}</td>
                <td class="px-4 py-3">{{ deal.category }}</td>
                <td class="px-4 py-3">
                    {% if status == "published" %}
                    <span class="text-green-600">✅ פורסם</span>
                    {% elif status == "queued" %}
                    <span class="text-blue-600">⏳ בתור</span>
                    {% else %}
                    <span class="text-gray-500">{{ status }}</span>
                    {% endif %}
                </td>
                <td class="px-4 py-3 text-gray-500">{{ deal.created_at.strftime("%H:%M") }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

- [ ] **Step 4: Implement dashboard/routes.py (index route only for now)**

```python
"""Dashboard route handlers."""

from __future__ import annotations

import datetime

from fastapi import FastAPI, Request
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
                stats = DailyStat(date=today)

            queue_count = session.execute(
                select(func.count())
                .select_from(PublishQueueItem)
                .where(PublishQueueItem.status == "queued")
            ).scalar() or 0

            # Recent deals with their publish status
            recent_rows = session.execute(
                select(Deal, PublishQueueItem.status)
                .outerjoin(PublishQueueItem, Deal.id == PublishQueueItem.deal_id)
                .order_by(Deal.created_at.desc())
                .limit(20)
            ).all()

            return templates.TemplateResponse("index.html", {
                "request": request,
                "stats": stats,
                "queue_count": queue_count,
                "recent_deals": recent_rows,
                "auto_refresh": config.dashboard.auto_refresh_seconds,
            })
        finally:
            session.close()
```

- [ ] **Step 5: Commit**

```bash
git add dashboard/app.py dashboard/routes.py dashboard/templates/base.html dashboard/templates/index.html
git commit -m "feat: dashboard base setup with main page showing stats and recent deals"
```

---

### Task 16: Dashboard — Deal Pages

**Files:**
- Create: `dashboard/templates/deals.html`
- Create: `dashboard/templates/deal_detail.html`
- Modify: `dashboard/routes.py` — add `/deals` and `/deals/{id}` routes

- [ ] **Step 1: Create dashboard/templates/deals.html**

```html
{% extends "base.html" %}
{% block title %}AliBot — דילים{% endblock %}
{% block content %}
<h2 class="text-lg font-semibold mb-4">כל הדילים</h2>

<form method="get" class="flex gap-3 mb-4 items-end">
    <div>
        <label class="block text-sm text-gray-500 mb-1">סטטוס</label>
        <select name="status" class="border rounded px-3 py-1.5 text-sm">
            <option value="">הכל</option>
            <option value="queued" {{ 'selected' if filter_status == 'queued' }}>בתור</option>
            <option value="published" {{ 'selected' if filter_status == 'published' }}>פורסם</option>
            <option value="failed" {{ 'selected' if filter_status == 'failed' }}>נכשל</option>
        </select>
    </div>
    <div>
        <label class="block text-sm text-gray-500 mb-1">קטגוריה</label>
        <select name="category" class="border rounded px-3 py-1.5 text-sm">
            <option value="">הכל</option>
            {% for cat in categories %}
            <option value="{{ cat }}" {{ 'selected' if filter_category == cat }}>{{ cat }}</option>
            {% endfor %}
        </select>
    </div>
    <button type="submit" class="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">סנן</button>
</form>

<div class="bg-white rounded-lg shadow overflow-hidden">
    <table class="w-full text-sm">
        <thead class="bg-gray-50">
            <tr>
                <th class="px-4 py-3 text-right">#</th>
                <th class="px-4 py-3 text-right">מוצר</th>
                <th class="px-4 py-3 text-right">מחיר</th>
                <th class="px-4 py-3 text-right">קטגוריה</th>
                <th class="px-4 py-3 text-right">מקור</th>
                <th class="px-4 py-3 text-right">סטטוס</th>
                <th class="px-4 py-3 text-right">זמן</th>
            </tr>
        </thead>
        <tbody class="divide-y">
            {% for deal, status in deals %}
            <tr class="hover:bg-gray-50">
                <td class="px-4 py-3 text-gray-400">{{ deal.id }}</td>
                <td class="px-4 py-3">
                    <a href="/deals/{{ deal.id }}" class="text-blue-600 hover:underline">{{ deal.product_name[:50] }}</a>
                </td>
                <td class="px-4 py-3">{{ "₪" if deal.currency == "ILS" else "$" }}{{ deal.price }}</td>
                <td class="px-4 py-3">{{ deal.category }}</td>
                <td class="px-4 py-3 text-gray-500">{{ deal.source_group }}</td>
                <td class="px-4 py-3">
                    {% if status == "published" %}<span class="text-green-600">✅</span>
                    {% elif status == "queued" %}<span class="text-blue-600">⏳</span>
                    {% elif status == "failed" %}<span class="text-red-600">❌</span>
                    {% else %}<span class="text-gray-400">—</span>{% endif %}
                </td>
                <td class="px-4 py-3 text-gray-500">{{ deal.created_at.strftime("%d/%m %H:%M") }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

- [ ] **Step 2: Create dashboard/templates/deal_detail.html**

```html
{% extends "base.html" %}
{% block title %}AliBot — דיל #{{ deal.id }}{% endblock %}
{% block content %}
<a href="/deals" class="text-blue-600 hover:underline text-sm">← חזרה לרשימה</a>

<div class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-6">
    <div class="bg-white rounded-lg shadow p-6">
        <h2 class="font-semibold text-lg mb-4">פרטי דיל #{{ deal.id }}</h2>
        <dl class="space-y-3 text-sm">
            <div><dt class="text-gray-500">מוצר</dt><dd class="font-medium">{{ deal.product_name }}</dd></div>
            <div><dt class="text-gray-500">מחיר</dt><dd>{{ "₪" if deal.currency == "ILS" else "$" }}{{ deal.price }}{% if deal.original_price %} <s class="text-gray-400">{{ deal.original_price }}</s>{% endif %}</dd></div>
            <div><dt class="text-gray-500">קטגוריה</dt><dd>{{ deal.category }}</dd></div>
            <div><dt class="text-gray-500">משלוח</dt><dd>{{ deal.shipping or "—" }}</dd></div>
            <div><dt class="text-gray-500">מקור</dt><dd>{{ deal.source_group }}</dd></div>
            <div><dt class="text-gray-500">לינק</dt><dd><a href="{{ deal.product_link }}" target="_blank" class="text-blue-600 hover:underline break-all">{{ deal.product_link[:60] }}...</a></dd></div>
            <div><dt class="text-gray-500">זמן יצירה</dt><dd>{{ deal.created_at.strftime("%d/%m/%Y %H:%M") }}</dd></div>
        </dl>
    </div>

    <div class="space-y-4">
        <div class="bg-white rounded-lg shadow p-6">
            <h3 class="font-semibold mb-2">טקסט מקורי</h3>
            <pre class="text-sm bg-gray-50 p-3 rounded whitespace-pre-wrap">{{ deal.original_text }}</pre>
        </div>
        <div class="bg-white rounded-lg shadow p-6">
            <h3 class="font-semibold mb-2">טקסט משוכתב</h3>
            <pre class="text-sm bg-blue-50 p-3 rounded whitespace-pre-wrap">{{ deal.rewritten_text }}</pre>
        </div>
    </div>
</div>

{% if queue_item %}
<div class="mt-6 bg-white rounded-lg shadow p-6">
    <h3 class="font-semibold mb-2">סטטוס פרסום</h3>
    <div class="text-sm space-y-1">
        <div>סטטוס: <strong>{{ queue_item.status }}</strong></div>
        <div>קבוצת יעד: {{ queue_item.target_group }}</div>
        {% if queue_item.published_at %}
        <div>פורסם: {{ queue_item.published_at.strftime("%d/%m/%Y %H:%M") }}</div>
        {% endif %}
        {% if queue_item.error_message %}
        <div class="text-red-600">שגיאה: {{ queue_item.error_message }}</div>
        {% endif %}
    </div>
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Add routes to dashboard/routes.py**

Append to the `register_routes` function in `dashboard/routes.py`:

```python
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

            return templates.TemplateResponse("deals.html", {
                "request": request,
                "deals": deals,
                "categories": categories,
                "filter_status": status,
                "filter_category": category,
            })
        finally:
            session.close()

    @app.get("/deals/{deal_id}")
    async def deal_detail(request: Request, deal_id: int):
        session = app.state.session_factory()
        templates = app.state.templates

        try:
            deal = session.get(Deal, deal_id)
            if deal is None:
                return templates.TemplateResponse("index.html", {
                    "request": request,
                    "stats": DailyStat(date=datetime.date.today()),
                    "queue_count": 0,
                    "recent_deals": [],
                }, status_code=404)

            queue_item = session.execute(
                select(PublishQueueItem)
                .where(PublishQueueItem.deal_id == deal_id)
                .limit(1)
            ).scalar_one_or_none()

            return templates.TemplateResponse("deal_detail.html", {
                "request": request,
                "deal": deal,
                "queue_item": queue_item,
            })
        finally:
            session.close()
```

- [ ] **Step 4: Commit**

```bash
git add dashboard/templates/deals.html dashboard/templates/deal_detail.html dashboard/routes.py
git commit -m "feat: dashboard deal list with filters and deal detail page"
```

---

### Task 17: Dashboard — Queue & Stats Pages

**Files:**
- Create: `dashboard/templates/queue.html`
- Modify: `dashboard/routes.py` — add `/queue` route with skip/promote actions

- [ ] **Step 1: Create dashboard/templates/queue.html**

```html
{% extends "base.html" %}
{% block title %}AliBot — תור פרסום{% endblock %}
{% block content %}
<h2 class="text-lg font-semibold mb-4">תור פרסום ({{ items | length }} דילים)</h2>

<div class="bg-white rounded-lg shadow overflow-hidden">
    <table class="w-full text-sm">
        <thead class="bg-gray-50">
            <tr>
                <th class="px-4 py-3 text-right">דיל</th>
                <th class="px-4 py-3 text-right">מוצר</th>
                <th class="px-4 py-3 text-right">יעד</th>
                <th class="px-4 py-3 text-right">עדיפות</th>
                <th class="px-4 py-3 text-right">מתוזמן אחרי</th>
                <th class="px-4 py-3 text-right">פעולות</th>
            </tr>
        </thead>
        <tbody class="divide-y">
            {% for qi, deal in items %}
            <tr class="hover:bg-gray-50">
                <td class="px-4 py-3 text-gray-400">#{{ deal.id }}</td>
                <td class="px-4 py-3">
                    <a href="/deals/{{ deal.id }}" class="text-blue-600 hover:underline">{{ deal.product_name[:40] }}</a>
                </td>
                <td class="px-4 py-3">{{ qi.target_group }}</td>
                <td class="px-4 py-3">{{ qi.priority }}</td>
                <td class="px-4 py-3 text-gray-500">{{ qi.scheduled_after.strftime("%H:%M") }}</td>
                <td class="px-4 py-3 flex gap-2">
                    <form method="post" action="/queue/{{ qi.id }}/skip" class="inline">
                        <button type="submit" class="text-red-600 hover:underline text-xs">דלג</button>
                    </form>
                    <form method="post" action="/queue/{{ qi.id }}/promote" class="inline">
                        <button type="submit" class="text-green-600 hover:underline text-xs">קדם</button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

- [ ] **Step 2: Add queue routes to dashboard/routes.py**

Append to the `register_routes` function:

```python
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

            return templates.TemplateResponse("queue.html", {
                "request": request,
                "items": items,
            })
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

        from starlette.responses import RedirectResponse
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

        from starlette.responses import RedirectResponse
        return RedirectResponse(url="/queue", status_code=303)
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/templates/queue.html dashboard/routes.py
git commit -m "feat: dashboard queue page with skip and promote actions"
```

---

### Task 18: Dashboard — Settings & Logs Pages

**Files:**
- Create: `dashboard/templates/settings.html`
- Create: `dashboard/templates/logs.html`
- Modify: `dashboard/routes.py` — add `/settings` and `/logs` routes

- [ ] **Step 1: Create dashboard/templates/settings.html**

```html
{% extends "base.html" %}
{% block title %}AliBot — הגדרות{% endblock %}
{% block content %}
<h2 class="text-lg font-semibold mb-4">הגדרות (קריאה בלבד)</h2>

<div class="grid grid-cols-1 md:grid-cols-2 gap-6">
    <div class="bg-white rounded-lg shadow p-6">
        <h3 class="font-semibold mb-3">טלגרם</h3>
        <dl class="text-sm space-y-2">
            <div><dt class="text-gray-500">קבוצות מקור</dt>
                <dd>{% for g in config.telegram.source_groups %}
                    <span class="bg-gray-100 rounded px-2 py-0.5 text-xs ms-1">{{ g }}</span>
                {% endfor %}</dd>
            </div>
            <div><dt class="text-gray-500">קבוצות יעד</dt>
                <dd>{% for k, v in config.telegram.target_groups.items() %}
                    <div><span class="text-gray-400">{{ k }}:</span> {{ v }}</div>
                {% endfor %}</dd>
            </div>
        </dl>
    </div>

    <div class="bg-white rounded-lg shadow p-6">
        <h3 class="font-semibold mb-3">פרסום</h3>
        <dl class="text-sm space-y-2">
            <div><dt class="text-gray-500">דיליי מינימלי</dt><dd>{{ config.publishing.min_delay_seconds }} שניות</dd></div>
            <div><dt class="text-gray-500">מקסימום לשעה</dt><dd>{{ config.publishing.max_posts_per_hour }}</dd></div>
            <div><dt class="text-gray-500">שעות שקט</dt><dd>{{ config.publishing.quiet_hours_start }}:00 — {{ config.publishing.quiet_hours_end }}:00</dd></div>
        </dl>
    </div>

    <div class="bg-white rounded-lg shadow p-6">
        <h3 class="font-semibold mb-3">כפילויות</h3>
        <dl class="text-sm space-y-2">
            <div><dt class="text-gray-500">חלון זמן</dt><dd>{{ config.dedup.window_hours }} שעות</dd></div>
            <div><dt class="text-gray-500">סף תמונה</dt><dd>{{ config.dedup.image_hash_threshold }}</dd></div>
        </dl>
    </div>

    <div class="bg-white rounded-lg shadow p-6">
        <h3 class="font-semibold mb-3">ווטרמארק</h3>
        <dl class="text-sm space-y-2">
            <div><dt class="text-gray-500">מיקום</dt><dd>{{ config.watermark.position }}</dd></div>
            <div><dt class="text-gray-500">שקיפות</dt><dd>{{ (config.watermark.opacity * 100) | int }}%</dd></div>
            <div><dt class="text-gray-500">גודל</dt><dd>{{ (config.watermark.scale * 100) | int }}%</dd></div>
        </dl>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Create dashboard/templates/logs.html**

```html
{% extends "base.html" %}
{% block title %}AliBot — לוגים{% endblock %}
{% block content %}
<h2 class="text-lg font-semibold mb-4">לוגים אחרונים</h2>
<div class="bg-white rounded-lg shadow p-4">
    <pre class="text-xs font-mono bg-gray-900 text-green-400 p-4 rounded overflow-x-auto max-h-[600px] overflow-y-auto" dir="ltr">{{ log_content }}</pre>
</div>
{% endblock %}
```

- [ ] **Step 3: Add settings and logs routes to dashboard/routes.py**

Append to the `register_routes` function:

```python
    @app.get("/settings")
    async def settings_page(request: Request):
        templates = app.state.templates
        config = app.state.config

        return templates.TemplateResponse("settings.html", {
            "request": request,
            "config": config,
        })

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

        return templates.TemplateResponse("logs.html", {
            "request": request,
            "log_content": log_content,
        })
```

- [ ] **Step 4: Wire dashboard into main.py**

Add to `main.py`, after the scheduler setup and before `client.run_until_disconnected()`:

```python
    # Dashboard
    import uvicorn
    from dashboard.app import create_dashboard

    dashboard_app = create_dashboard(SessionFactory, config)
    uvicorn_config = uvicorn.Config(
        dashboard_app,
        host="0.0.0.0",
        port=config.dashboard.port,
        log_level="warning",
    )
    server = uvicorn.Server(uvicorn_config)
    asyncio.create_task(server.serve())
    logger.info(f"Dashboard running on http://0.0.0.0:{config.dashboard.port}")
```

- [ ] **Step 5: Commit**

```bash
git add dashboard/templates/settings.html dashboard/templates/logs.html dashboard/routes.py main.py
git commit -m "feat: dashboard settings, logs pages, and wired into main entry point"
```

---

## Post-Plan: Manual Verification Checklist

After all tasks are complete, run through this manually:

- [ ] `pip install -r requirements.txt` installs without errors
- [ ] `python -m pytest tests/ -v` — all tests pass
- [ ] `python -m pytest tests/ --cov=bot --cov-report=term-missing` — coverage >80%
- [ ] Create `.env` from `.env.example` with real Telegram credentials
- [ ] Create a test logo at `assets/logo.png`
- [ ] `python main.py` — bot starts, connects to Telegram, prints "Bot is running!"
- [ ] Send a test deal in a source group — confirm it appears in DB
- [ ] Wait for publisher cycle — confirm it posts to target channel
- [ ] Send `/stats` from admin account — confirm response
- [ ] Open `http://<mac-mini-ip>:8080` — confirm dashboard loads
