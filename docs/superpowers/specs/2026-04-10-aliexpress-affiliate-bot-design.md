# AliExpress Affiliate Deal Bot — Design Spec

## Overview

Automated Telegram bot that listens to Hebrew deal groups, processes each deal (dedup, AI rewrite, watermark, affiliate link), and publishes to our own channel at a controlled pace.

**Goal:** Passive income from AliExpress affiliate commissions with zero manual work.

**Scope:** This spec covers MVP Phase 1a (core pipeline) and Phase 1b (web dashboard). Future phases (AliExpress API, WhatsApp, multi-channel routing) are referenced for extensibility but not specified in detail.

---

## Architecture

### Single Process, Two Loops

One async Python process running on a Mac mini (local network, 24/7):

**Processing Loop** (event-driven, immediate):
```
Telegram Message → Save Raw → Parser → Dedup Check → Link Resolver
    → AI Rewrite + Categorize → Image Processor (watermark) → Enqueue
```

**Publishing Loop** (scheduler, controlled pace):
```
Every 2-3 min: pick oldest queued deal → publish to target channel
    → mark published → random 5-10 min delay → next deal
```

Key properties:
- Processing is fast and event-driven (don't lose deals)
- Publishing is slow and controlled (don't look like a copy-bot)
- Raw messages always saved to DB before processing (crash safety)
- If process restarts, queued deals remain in DB waiting to publish
- Quiet hours (23:00-07:00): processing continues, publishing pauses

### Component Map

| Component | File | Responsibility |
|-----------|------|----------------|
| Listener | `listener.py` | Telethon event handler, saves raw messages |
| Parser | `parser.py` | Extract price, link, images from message |
| Dedup | `dedup.py` | Product ID + text hash + image hash check |
| Resolver | `resolver.py` | s.click short links → product ID |
| Rewriter | `rewriter.py` | OpenAI rewrite + categorization |
| ImageProcessor | `image_processor.py` | Download images, add watermark |
| Publisher | `publisher.py` | Pick from queue, post to channel |
| Notifier | `notifier.py` | Error alerts + daily summary to admin |
| Models | `models.py` | SQLAlchemy models |
| Config | `config.py` | Load & validate config.yaml |
| Dashboard | `dashboard.py` | FastAPI web UI (Phase 1b) |
| Admin | `admin.py` | Telegram admin commands |

### Extensibility Points (designed now, built later)

- **Source groups:** Stored in config, easy to add. Phase 2: dynamic add via Telegram command.
- **Target groups + routing:** `deal.category` → group mapping in config. MVP sends everything to one channel. Phase 2: route by category.
- **AliExpress API:** Affiliate link generation is an interface. MVP uses direct product link. Swap to API when approved.
- **WhatsApp publisher:** Publisher is abstract. Add `WhatsAppPublisher` implementing the same interface.
- **Web dashboard:** Phase 1b, runs on same process.

---

## Data Model (SQLite + SQLAlchemy)

### raw_messages
Raw Telegram messages saved immediately for crash safety.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| source_group | TEXT | @groupname |
| telegram_message_id | INTEGER | |
| raw_text | TEXT | |
| has_images | BOOLEAN | |
| received_at | TIMESTAMP | |
| status | TEXT | pending / processed / failed |
| error_message | TEXT | nullable, if processing failed |

### deals
Processed deals with all extracted and generated data.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| raw_message_id | INTEGER FK | → raw_messages |
| product_id | TEXT UNIQUE | AliExpress product ID (nullable until resolved) |
| product_name | TEXT | |
| original_text | TEXT | original message text |
| rewritten_text | TEXT | AI-rewritten text |
| price | REAL | |
| original_price | REAL | nullable, price before discount |
| currency | TEXT | ILS / USD |
| shipping | TEXT | |
| category | TEXT | tech / home / fashion / etc. |
| affiliate_link | TEXT | nullable until API approved |
| product_link | TEXT | direct AliExpress link |
| image_hash | TEXT | perceptual hash for dedup |
| text_hash | TEXT | MD5 of normalized product name |
| source_group | TEXT | |
| created_at | TIMESTAMP | |

Indexes: `product_id` (unique), `image_hash`, `text_hash`, `created_at`

### publish_queue
Publishing queue with scheduling and priority support.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| deal_id | INTEGER FK | → deals |
| target_group | TEXT | where to publish |
| status | TEXT | queued / publishing / published / failed |
| priority | INTEGER | default 0, higher = publish first |
| scheduled_after | TIMESTAMP | don't publish before this time |
| published_at | TIMESTAMP | nullable |
| message_id | INTEGER | Telegram message ID after posting |
| error_message | TEXT | nullable |

Index: `(status, scheduled_after)` — publisher queries this

### daily_stats
Aggregated daily statistics.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| date | DATE UNIQUE | |
| deals_seen | INTEGER | default 0 |
| deals_processed | INTEGER | default 0 |
| deals_published | INTEGER | default 0 |
| deals_skipped_dup | INTEGER | default 0 |
| deals_skipped_error | INTEGER | default 0 |
| api_calls | INTEGER | default 0 |

---

## Component Details

### Listener
- Telethon client with dedicated user account (not Bot API)
- Listens to all source groups simultaneously via single event handler
- Every incoming message → save to `raw_messages` immediately → pass to pipeline
- Auto-reconnect (Telethon built-in)
- Filters: ignores messages shorter than 20 chars, messages without links, message edits

### Parser
- Regex for AliExpress links: `aliexpress.com`, `s.click.aliexpress.com`, `a.aliexpress.com`
- Regex for prices: patterns with `₪`, `ש"ח`, `$`, `NIS`, `ILS` + number
- Extracts images from message media (Telethon `message.media`)
- No AliExpress link found → skip (not every message is a deal)

### Dedup (3-Layer Check)
Within a configurable time window (default 24h):

1. **Product ID** — exact match in DB (most accurate, not always available)
2. **Text hash** — MD5 of normalized product name (lowercase, stripped whitespace)
3. **Image hash** — perceptual hash (dhash via `imagehash` library), threshold < 5

Duplicate = skip + increment `daily_stats.deals_skipped_dup`.

### Link Resolver
- `httpx` async client with `follow_redirects=True`
- Resolves `s.click.aliexpress.com/e/XXX` → follows redirects → extracts product ID from final URL
- Caches resolved URLs in DB (don't resolve same link twice)
- Timeout: 10 seconds → skip + log error
- Fallback: HEAD request if GET fails

### Rewriter (OpenAI)
Single API call that returns structured JSON:

```json
{
  "rewritten_text": "Hebrew deal text with emojis",
  "category": "tech",
  "product_name_clean": "cleaned product name for dedup"
}
```

- Model: `gpt-4o-mini` (good Hebrew, ~$0.001/deal)
- Uses JSON mode (structured output) to prevent parsing issues
- System prompt instructs: rewrite in Hebrew, change phrasing completely, keep all facts, add emojis, 3-6 lines, mention price/shipping/rating

### Image Processor
- Downloads images from Telegram message (not from AliExpress CDN — avoids referer blocking)
- Adds watermark: transparent PNG logo overlay
  - Position: configurable (default bottom-right)
  - Opacity: configurable (default 40%)
  - Scale: 15% of image width
- Resize if image exceeds Telegram's 10MB limit
- Pillow for all processing
- Logo file: `assets/logo.png` (user provides)

### Publisher
- APScheduler job runs every 2-3 minutes
- Queries `publish_queue` for oldest deal where `status=queued` and `scheduled_after < now`
- Sends via Telethon: image + rewritten text + link (inline button "לרכישה")
- After publishing: random delay 5-10 min before next deal
- Rate limits:
  - Max 4 posts/hour per group
  - Quiet hours: 23:00-07:00 (deals wait until morning)
  - Exponential backoff on Telegram 429 errors
- Updates `publish_queue.status` to "published" and records `message_id`

### Notifier
- **Critical errors:** Telegram message to admin's Saved Messages on pipeline crash, disconnect, API failure
- **Daily summary** at 21:00: deals seen, processed, published, skipped, queue size
- Uses same Telethon client

### Admin Commands (Telegram)
Listens to messages from admin user only (identified by Telegram user ID in config):

| Command | Action |
|---------|--------|
| `/stats` | Today's statistics |
| `/pause` | Stop publishing (processing continues) |
| `/resume` | Resume publishing |
| `/queue` | Number of deals in queue |
| `/skip [id]` | Skip a specific deal |
| `/last` | Last 5 published deals |

---

## Web Dashboard (Phase 1b)

**Stack:** FastAPI + Jinja2 templates + Tailwind CSS, running on port 8080 on the same process.

**No authentication in MVP** (local network only). Phase 2: basic auth.

### Routes

| Route | Content |
|-------|---------|
| `/` | Main dashboard — stats, status (running/paused), recent deals |
| `/deals` | Deal table with filters (status, category, date) |
| `/deals/{id}` | Deal detail: original text, rewritten, image, status |
| `/queue` | Publish queue — waiting deals, skip/promote buttons |
| `/settings` | Current config (read-only in MVP) |
| `/logs` | Last 100 log lines |

### UI Properties
- RTL layout (Hebrew UI, `dir="rtl"`)
- Auto-refresh every 30 seconds
- Mobile-friendly (Tailwind responsive)
- No JavaScript framework — server-rendered HTML

---

## Configuration

### config.yaml

```yaml
telegram:
  api_id: ${TELEGRAM_API_ID}
  api_hash: ${TELEGRAM_API_HASH}
  phone: "+972XXXXXXXXX"
  
  source_groups:
    - "@group1"
    - "@group2"
    - "@group3"
  
  target_groups:
    default: "@my_deals_channel"
  
  admin_chat: "me"  # Saved Messages
  admin_user_id: 123456789  # Your Telegram user ID (for admin commands)

openai:
  api_key: ${OPENAI_API_KEY}
  model: "gpt-4o-mini"

aliexpress:
  # Phase 2 — populated when API approved
  app_key: ${ALIEXPRESS_APP_KEY}
  app_secret: ${ALIEXPRESS_APP_SECRET}
  tracking_id: ${ALIEXPRESS_TRACKING_ID}

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

All secrets via environment variables, never in the config file.

---

## File Structure

```
alibot/
├── main.py                    # Entry point, wires everything together
├── config.yaml                # Configuration (no secrets)
├── requirements.txt
├── .env.example               # Template for environment variables
├── assets/
│   └── logo.png               # Watermark logo (user provides)
├── bot/
│   ├── __init__.py
│   ├── config.py              # Load & validate config
│   ├── models.py              # SQLAlchemy models
│   ├── listener.py            # Telegram listener
│   ├── parser.py              # Deal parser
│   ├── dedup.py               # Duplicate checker
│   ├── resolver.py            # Link resolver
│   ├── rewriter.py            # AI content rewriter
│   ├── image_processor.py     # Watermark & image handling
│   ├── publisher.py           # Queue-based publisher
│   ├── notifier.py            # Error alerts & daily summary
│   ├── admin.py               # Telegram admin commands
│   └── pipeline.py            # Orchestrates the processing pipeline
├── dashboard/
│   ├── __init__.py
│   ├── app.py                 # FastAPI app
│   ├── routes.py              # Route handlers
│   └── templates/
│       ├── base.html           # Base template (RTL, Tailwind)
│       ├── index.html          # Main dashboard
│       ├── deals.html          # Deal list
│       ├── deal_detail.html    # Single deal view
│       ├── queue.html          # Publish queue
│       ├── settings.html       # Config viewer
│       └── logs.html           # Log viewer
├── data/
│   ├── deals.db               # SQLite database (auto-created)
│   └── images/                # Cached processed images
└── tests/
    ├── test_parser.py
    ├── test_dedup.py
    ├── test_resolver.py
    ├── test_rewriter.py
    └── test_image_processor.py
```

---

## Tech Stack

```
Python 3.10+
├── Telethon            # Telegram client (user account)
├── SQLAlchemy          # Database ORM
├── httpx               # Async HTTP client
├── openai              # AI content rewriting
├── Pillow              # Image processing
├── imagehash           # Duplicate detection (perceptual hash)
├── APScheduler         # Scheduled publishing
├── FastAPI             # Web dashboard
├── Jinja2              # HTML templates
├── pyyaml              # Config file
├── loguru              # Logging
├── uvicorn             # ASGI server for FastAPI
└── python-dotenv       # Environment variables
```

---

## Phasing

### Phase 1a — Core Pipeline (Weeks 1-2)
- Telegram listener (2-3 source groups)
- Message parser (regex)
- Duplicate checker (product ID + text hash + image hash)
- Link resolver (short URL → product ID)
- AI rewriter (gpt-4o-mini, Hebrew, with categorization)
- Image processor (watermark)
- Queue-based publisher (one target channel)
- Telegram admin commands (/stats, /pause, /resume, /queue, /skip, /last)
- Notifier (critical errors + daily summary)
- Direct product links (no affiliate until API approved)

### Phase 1b — Web Dashboard (Week 3)
- FastAPI dashboard on port 8080
- Deal list, queue view, stats, logs, settings
- RTL Hebrew UI with Tailwind CSS
- Local network access only

### Phase 2 — API & Scale (Month 2)
- AliExpress Affiliate API integration (product details + affiliate links)
- Dynamic source group management (Telegram commands)
- Multiple target channels with category-based routing
- Image dedup improvements
- Dashboard auth (basic auth)
- Dashboard: editable settings, deal approval workflow

### Phase 3 — Multi-Platform (Month 3+)
- WhatsApp publisher
- Facebook posting
- Price tracking & alerts
- Smart scheduling (peak hours analysis)
- Advanced analytics (click tracking, revenue)

---

## Known Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Telegram account ban | Pipeline stops | Dedicated account, conservative rate limits, random delays |
| AliExpress API rejection | No affiliate revenue | Bot runs without affiliate links, reapply with active channel as proof |
| OpenAI API down | No rewriting | Queue deals, retry when API recovers; fallback: template-based rewrite |
| Source group goes private/deleted | Fewer deals | Monitor and notify admin; easy to add replacement groups |
| Duplicate detection false negatives | Same deal posted twice | 3-layer check minimizes risk; 24h window is conservative |
| Duplicate detection false positives | Good deals skipped | Configurable thresholds; start conservative, loosen if needed |
