# PRD - AliExpress Affiliate Deal Bot

## Product Overview

בוט אוטומטי שמאזין לקבוצות דילים בטלגרם, מעבד כל דיל (סינון כפילויות, שכתוב AI, החלפת לינק אפיליאט, שליפת תמונות), ומפרסם בקבוצות שלנו.

**מטרה:** הכנסה פאסיבית מעמלות AliExpress Affiliate בלי עבודה ידנית.

---

## מחקר שוק

### פרויקטים קיימים (השראה)
- [MiilouDz/Aliexpress-Affiliate-Telegram-Bot](https://github.com/MiilouDz/Aliexpress-Affiliate-Telegram-Bot) - בוט בסיסי, Python
- [SaulloGabryel/BlueBot](https://github.com/SaulloGabryel/BlueBot) - מולטי-פלטפורמה (טלגרם+ווטסאפ), רץ חודשים על VPS
- [hectorzin/botaffiumeiro](https://github.com/hectorzin/botaffiumeiro) - מזהה לינקים ומחליף אוטומטית

### הזדמנות
- ערוצי דילים בטלגרם עם עשרות אלפי עוקבים
- עמלות AliExpress עד 9% עם cookie של 30 יום
- הכנסה טיפוסית מערוץ טלגרם: $200-500/חודש
- אוטומציה חוסכת שעות של עבודה ידנית יומית

---

## Architecture

```
┌─────────────────────────┐
│  קבוצות מקור (טלגרם)    │  10+ קבוצות דילים
└──────────┬──────────────┘
           │ Telethon listener
           ▼
┌─────────────────────────┐
│  Message Parser          │  חילוץ: מוצר, מחיר, לינק, תמונה
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│  Duplicate Checker       │  SQLite + imagehash + text hash
│  (24h window)            │  כפילות? → דלג
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│  Link Resolver           │  s.click.aliexpress.com → product ID
│                          │  HTTP redirect follow
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│  AliExpress API          │  שליפת: תמונות HD, מחיר, דירוג,
│  Product Details         │  מכירות, תיאור
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│  Affiliate Link Gen      │  AliExpress Affiliate API
│                          │  get_affiliate_links()
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│  AI Content Rewriter     │  OpenAI API / Open Router
│                          │  שכתוב בעברית, סגנון חדש
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│  Publisher                │  Telethon → קבוצות יעד
│  (rate limited)          │  תמונה + טקסט + לינק
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│  Analytics & Logging     │  מה פורסם, clicks, הכנסות
└─────────────────────────┘
```

---

## Components

### 1. Telegram Listener (Telethon)

```python
# לא bot API - חשבון טלגרם רגיל עם Telethon
# כדי להאזין לקבוצות שאתה חבר בהן

class TelegramListener:
    """Listen to deal groups and capture new posts."""

    config:
        - phone_number: str          # מספר טלפון לחיבור
        - api_id: int                # Telegram API ID
        - api_hash: str              # Telegram API hash
        - source_groups: list[str]   # רשימת קבוצות מקור
        - min_message_length: int    # מינימום אורך (סינון spam)

    events:
        - on_new_deal(message, images) → Pipeline
```

**חשוב:** צריך Telegram API credentials מ-my.telegram.org (חינם).

### 2. Message Parser

```python
class DealParser:
    """Extract deal components from raw message."""

    input: raw telegram message (text + images)

    output:
        - product_name: str        # שם המוצר
        - price: float             # מחיר בש"ח
        - original_price: float    # מחיר מקורי (אם יש)
        - currency: str            # ILS/USD
        - shipping: str            # "חינם" / מחיר
        - link: str                # לינק AliExpress
        - images: list[bytes]      # תמונות שצורפו
        - rating: float            # דירוג (אם צוין)
        - sales_count: int         # מכירות (אם צוין)
        - category: str            # קטגוריה (AI)

    logic:
        - regex לחילוץ מחיר (₪, ש"ח, $, NIS)
        - regex לחילוץ לינק aliexpress
        - AI לזיהוי שם מוצר וקטגוריה
```

### 3. Duplicate Checker

```python
class DuplicateChecker:
    """Prevent posting same deal twice in 24h."""

    storage: SQLite

    methods:
        - check_text_hash(product_name) → bool
        - check_image_hash(image_bytes) → bool   # imagehash library
        - check_product_id(ali_product_id) → bool
        - mark_as_posted(deal) → None
        - cleanup_old(hours=24) → None

    strategy:
        1. Product ID exact match (best)
        2. Text similarity (Levenshtein > 0.8)
        3. Image perceptual hash (dhash, threshold < 5)
```

### 4. Link Resolver

```python
class LinkResolver:
    """Resolve s.click.aliexpress.com to product ID."""

    input: "https://s.click.aliexpress.com/e/_oEhUSd4"
    output: "1005003091506814" (product ID)

    method:
        1. HTTP GET with allow_redirects=True
        2. Follow redirects until reaching aliexpress.com/item/XXX.html
        3. Extract product ID from final URL
        4. Cache: resolved URLs stored in DB (TTL 7 days)

    fallback:
        - If redirect fails, try HEAD request
        - If all fails, skip deal and log error
```

### 5. AliExpress API Client

```python
class AliExpressClient:
    """Interact with AliExpress Affiliate API."""

    credentials:
        - app_key: str
        - app_secret: str
        - tracking_id: str

    methods:
        get_product_details(product_id) → {
            title, price, sale_price, currency,
            images: [url1, url2, ...],   # HD images
            rating, orders_count,
            commission_rate, category
        }

        get_affiliate_link(product_url) → affiliate_url

        search_products(keyword, category) → [products]  # for future use

    rate_limit: 5,000/day, batch 50 URLs

    library: python-aliexpress-api
```

### 6. AI Content Rewriter

```python
class ContentRewriter:
    """Rewrite deal text using AI."""

    api: OpenAI / Open Router
    model: gpt-4o-mini (cheap, good Hebrew)

    prompt template:
        "אתה כותב תוכן לערוץ דילים בטלגרם.
        קיבלת דיל:
        מוצר: {product_name}
        מחיר: {price}
        משלוח: {shipping}
        דירוג: {rating}
        מכירות: {sales}

        כתוב פוסט דיל חדש בעברית. כללים:
        - שנה ניסוח לגמרי (לא copy)
        - שמור על כל המידע החשוב
        - הוסף אימוג'ים מתאימים
        - הוסף 3-5 נקודות חיוביות על המוצר
        - ציין מחיר, משלוח, דירוג
        - סגנון מושך ומזמין לרכישה
        - אורך: 3-6 שורות"

    output: טקסט מעוצב מוכן לפרסום

    cost estimate: ~$0.001 per deal (gpt-4o-mini)
```

### 7. Publisher

```python
class DealPublisher:
    """Publish deals to target groups."""

    config:
        - target_groups: dict[str, list[str]]  # category → groups
        - min_delay: int = 300                  # 5 min between posts
        - max_posts_per_hour: int = 4
        - quiet_hours: tuple = (23, 7)          # don't post at night

    method:
        1. Download product image from AliExpress
        2. Compose message: image + rewritten text + affiliate link
        3. Add inline button "🛒 לרכישה" with affiliate link
        4. Send to appropriate target group(s)
        5. Log: timestamp, group, product_id, link

    anti-spam:
        - Random delay: 300-600 seconds between posts
        - Max 4 posts/hour per group
        - No posting 23:00-07:00
        - Vary formatting slightly
```

### 8. Dashboard & Analytics

```python
class Analytics:
    """Track performance."""

    metrics:
        - deals_processed: int       # total deals seen
        - deals_posted: int          # after filtering
        - deals_skipped_duplicate: int
        - deals_skipped_no_link: int
        - posts_per_group: dict
        - api_calls_today: int

    reporting:
        - Daily summary to Telegram (personal chat)
        - Weekly report with top performing deals
```

---

## Database Schema (SQLite)

```sql
CREATE TABLE deals (
    id INTEGER PRIMARY KEY,
    product_id TEXT UNIQUE,
    product_name TEXT,
    price REAL,
    category TEXT,
    source_group TEXT,
    affiliate_link TEXT,
    image_hash TEXT,         -- perceptual hash
    text_hash TEXT,          -- MD5 of title
    posted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    deal_id INTEGER REFERENCES deals(id),
    target_group TEXT,
    message_id INTEGER,
    posted_at TIMESTAMP
);

CREATE TABLE stats (
    id INTEGER PRIMARY KEY,
    date DATE,
    deals_seen INTEGER,
    deals_posted INTEGER,
    deals_skipped INTEGER,
    api_calls INTEGER
);

CREATE INDEX idx_deals_product_id ON deals(product_id);
CREATE INDEX idx_deals_posted_at ON deals(posted_at);
CREATE INDEX idx_deals_image_hash ON deals(image_hash);
```

---

## Configuration File

```yaml
# config.yaml
telegram:
  api_id: YOUR_API_ID
  api_hash: YOUR_API_HASH
  phone: "+972XXXXXXXXX"

  source_groups:
    - "@haregakaniti"
    - "@deals_il"
    # ... more groups

  target_groups:
    general: "@my_deals_channel"
    tech: "@my_tech_deals"
    home: "@my_home_deals"

aliexpress:
  app_key: YOUR_APP_KEY
  app_secret: YOUR_APP_SECRET
  tracking_id: YOUR_TRACKING_ID

openai:
  api_key: YOUR_OPENAI_KEY
  model: gpt-4o-mini

publishing:
  min_delay_seconds: 300
  max_posts_per_hour: 4
  quiet_hours_start: 23
  quiet_hours_end: 7
  min_price_ils: 5        # ignore deals under 5 ILS
  max_price_ils: 500      # ignore very expensive items

duplicate:
  window_hours: 24
  image_hash_threshold: 5
  text_similarity_threshold: 0.8
```

---

## Tech Stack

```
Python 3.10+
├── Telethon            # Telegram client (user account, not bot)
├── python-aliexpress-api  # AliExpress API wrapper
├── openai              # AI content rewriting
├── Pillow              # Image processing
├── imagehash           # Duplicate detection
├── httpx               # HTTP client (async)
├── SQLAlchemy          # Database ORM
├── APScheduler         # Scheduled tasks
├── pyyaml              # Config file
└── loguru              # Logging
```

---

## Known Challenges & Solutions

### 1. s.click.aliexpress.com Link Resolution
**בעיה:** לינקים קצרים לא חושפים product ID
**פתרון:** HTTP follow redirects → extract from final URL
**Fallback:** אם נכשל, דלג על הדיל

### 2. AliExpress CDN Image Blocking
**בעיה:** תמונות מ-CDN של AliExpress נחסמות בגלל referer check
**פתרון:** תמיד להוריד תמונות לדיסק מקומי לפני שליחה

### 3. Telegram Rate Limiting
**בעיה:** שליחת יותר מדי הודעות = חסימה
**פתרון:**
- Random delay 5-10 דקות בין פוסטים
- מקסימום 4 פוסטים בשעה
- exponential backoff על HTTP 429

### 4. כפילויות Cross-Group
**בעיה:** אותו דיל מתפרסם ב-5 קבוצות מקור
**פתרון:** Product ID + image hash + text hash → DB check

### 5. ToS Risks
**בעיה:** AliExpress אוסר על "abnormal clicking/viewing"
**פתרון:**
- שיתוף דילים אמיתיים למשתמשים אמיתיים (לא click farm)
- לא ללחוץ על הלינקים שלנו
- posting frequency סביר

### 6. API Approval
**בעיה:** אישור AliExpress API לוקח 2-4 שבועות
**פתרון:** להגיש בקשה מיד, בינתיים לעבוד עם link shortener ידני

---

## Implementation Phases

### Phase 1: MVP (שבוע 1-2)
- [ ] Telegram listener על קבוצה אחת
- [ ] Message parser בסיסי (regex)
- [ ] Link resolver
- [ ] Duplicate check (product ID + text hash)
- [ ] Simple rewrite (template, לא AI)
- [ ] Publisher לקבוצה אחת
- [ ] Manual affiliate link (עד שה-API יאושר)

### Phase 2: AI + API (שבוע 3-4)
- [ ] AliExpress API integration (product details + affiliate links)
- [ ] AI content rewriting (OpenAI)
- [ ] Image handling (download from API + send)
- [ ] Image dedup (imagehash)
- [ ] Multiple source groups (5+)
- [ ] Analytics dashboard

### Phase 3: Scale (חודש 2)
- [ ] 10+ קבוצות מקור
- [ ] קבוצות יעד לפי קטגוריה
- [ ] WhatsApp integration
- [ ] Performance optimization
- [ ] A/B testing on content styles

### Phase 4: Advanced (חודש 3+)
- [ ] Facebook posting
- [ ] מודל AI מקומי (חיסכון עלויות)
- [ ] Price tracking (התראה כשמחיר יורד)
- [ ] Smart scheduling (פרסום בשעות שיא)
- [ ] Multi-platform analytics

---

## Cost Estimate (Monthly)

| Item | Cost |
|------|------|
| OpenAI API (gpt-4o-mini, ~1000 deals/month) | ~$1-3 |
| VPS (to run 24/7) | $5-10 |
| AliExpress API | Free |
| Telegram API | Free |
| **Total** | **$6-13/month** |

## Expected Revenue

| Scenario | Deals/Day | Clicks/Day | Conversions | Monthly Revenue |
|----------|-----------|------------|-------------|-----------------|
| Conservative | 10 | 50 | 2 | $50-100 |
| Moderate | 30 | 200 | 10 | $200-500 |
| Aggressive | 50+ | 500+ | 25+ | $500-2000 |

*Based on average order $20, 5% commission, 5% conversion rate*

---

## File Structure

```
aliexpress-bot/
├── config.yaml
├── main.py                    # Entry point
├── requirements.txt
├── bot/
│   ├── __init__.py
│   ├── listener.py            # Telegram listener
│   ├── parser.py              # Deal parser
│   ├── resolver.py            # Link resolver
│   ├── dedup.py               # Duplicate checker
│   ├── aliexpress_client.py   # AliExpress API
│   ├── rewriter.py            # AI content rewriter
│   ├── publisher.py           # Post to groups
│   ├── analytics.py           # Stats & reporting
│   └── models.py              # DB models
├── data/
│   ├── deals.db               # SQLite database
│   └── images/                # Cached images
└── tests/
    ├── test_parser.py
    ├── test_resolver.py
    └── test_dedup.py
```
