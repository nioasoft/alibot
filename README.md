# AliBot — בוט דילים אוטומטי לטלגרם ווואטסאפ

בוט שמאזין לקבוצות דילים בטלגרם, מעבד כל דיל (סינון כפילויות, שכתוב AI בעברית, לינק אפיליאט, watermark), ומפרסם בערוץ טלגרם ובקבוצת וואטסאפ.

## ארכיטקטורה

```
קבוצות מקור (7 קבוצות טלגרם)
        │
        ▼
   Telegram Listener (Telethon)
        │
        ▼
   Pipeline: Parse → Dedup → Resolve → AI Rewrite → Watermark → Queue
        │
        ▼
   Publisher (כל 3 דקות)
        │
   ┌────┴────┐
   ▼         ▼
Telegram   WhatsApp
 Channel    Group
```

בנוסף, כל 4 שעות הבוט שולף מוצרים טרנדיים מ-AliExpress API ומפרסם אותם.

## דרישות

- Python 3.10+ (על ה-Mac mini: 3.12 via Homebrew)
- Node.js 18+ (ל-WhatsApp service)
- חשבון טלגרם ייעודי (לא אישי)
- מספר טלפון ייעודי לוואטסאפ
- AliExpress Affiliate API credentials
- OpenAI API key

## מבנה הפרויקט

```
alibot/
├── main.py                     # Entry point — מחבר הכל ומפעיל
├── config.yaml                 # הגדרות (ללא סודות)
├── .env                        # סודות (API keys) — לא ב-git
├── requirements.txt            # Python dependencies
├── assets/
│   └── logo.png                # לוגו ל-watermark
├── bot/
│   ├── config.py               # טעינת config + env vars
│   ├── models.py               # SQLAlchemy models (4 טבלאות)
│   ├── listener.py             # Telethon — מאזין לקבוצות מקור
│   ├── parser.py               # חילוץ לינקים, מחירים, משלוח
│   ├── dedup.py                # בדיקת כפילויות (3 שכבות)
│   ├── resolver.py             # פתרון לינקים קצרים → product ID
│   ├── rewriter.py             # שכתוב AI בעברית (OpenAI)
│   ├── image_processor.py      # watermark + image hash
│   ├── aliexpress_client.py    # AliExpress API (אפיליאט + פרטי מוצר)
│   ├── pipeline.py             # תזמור כל שלבי העיבוד
│   ├── publisher.py            # פרסום מתור עם rate limiting
│   ├── hot_products.py         # שליפת מוצרים טרנדיים אוטומטית
│   ├── exchange_rate.py        # שער דולר-שקל יומי
│   ├── whatsapp_publisher.py   # שליחה לוואטסאפ דרך Baileys service
│   ├── notifier.py             # התראות שגיאה + סיכום יומי
│   └── admin.py                # פקודות admin מטלגרם
├── whatsapp/
│   ├── index.js                # Baileys WhatsApp microservice (Node.js)
│   ├── package.json
│   └── auth_state/             # WhatsApp session (לא ב-git)
├── dashboard/
│   ├── app.py                  # FastAPI app
│   ├── routes.py               # Route handlers
│   └── templates/              # Jinja2 HTML templates (RTL Hebrew)
├── data/
│   ├── deals.db                # SQLite database
│   ├── bot.session             # Telegram session
│   └── images/                 # תמונות מעובדות
└── tests/                      # 91 tests (pytest)
```

## הגדרות

### .env (סודות)

```
TELEGRAM_API_ID=<מ-my.telegram.org>
TELEGRAM_API_HASH=<מ-my.telegram.org>
TELEGRAM_PHONE=+972XXXXXXXXX
TELEGRAM_ADMIN_USER_ID=<מ-@userinfobot>

OPENAI_API_KEY=sk-proj-...

ALIEXPRESS_APP_KEY=<מ-portals.aliexpress.com>
ALIEXPRESS_APP_SECRET=<מ-portals.aliexpress.com>
ALIEXPRESS_TRACKING_ID=telegram
```

### config.yaml (הגדרות גלויות)

קבוצות מקור, קבוצות יעד, rate limits, watermark, ועוד. ערכים מרכזיים:

| הגדרה | ערך | הסבר |
|-------|-----|-------|
| `publishing.max_posts_per_hour` | 12 | מקסימום פרסומים בשעה |
| `publishing.min_delay_seconds` | 120 | דיליי מינימלי בין פרסומים (2 דקות) |
| `publishing.max_delay_seconds` | 240 | דיליי מקסימלי (4 דקות) |
| `publishing.quiet_hours_start/end` | 23/7 | שעות שקט (לא מפרסם) |
| `publishing.hot_products_interval_hours` | 4 | כל כמה שעות לשלוף מוצרים טרנדיים |
| `publishing.hot_products_per_run` | 3 | כמה מוצרים לשלוף בכל ריצה |
| `dedup.window_hours` | 24 | חלון כפילויות (שעות) |
| `watermark.opacity` | 0.4 | שקיפות הלוגו (40%) |

## הפעלה מקומית (פיתוח)

```bash
# Python
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# WhatsApp service
cd whatsapp && npm install && cd ..

# הפעלה
node whatsapp/index.js &          # WhatsApp service (port 3001)
PYTHONPATH=. python main.py       # Bot + Dashboard (port 8080)
```

בפעם הראשונה:
- Telethon יבקש קוד אימות לטלגרם
- Baileys יציג QR code לסריקה מוואטסאפ

## Mac mini — הפעלה ב-production

הבוט רץ על Mac mini (`10.0.0.26`) עם auto-start ו-auto-restart.

### מיקום על המיני

```
~/Projects/alibot/
```

### Services (launchd)

שלושה services רשומים ב-launchd:

| Service | מה הוא עושה | Log |
|---------|-------------|-----|
| `com.alibot.bot` | Python bot + Dashboard | `/tmp/alibot.log` |
| `com.alibot.whatsapp` | Node.js Baileys service | `/tmp/wa_service.log` |
| `com.alibot.facebook` | Node.js Playwright Facebook publisher | `/tmp/facebook_service.log` |

### פקודות שליטה (מרחוק דרך SSH)

```bash
# התחברות
ssh asafbenatia@10.0.0.26

# סטטוס
launchctl list | grep alibot

# עצירה
launchctl stop com.alibot.bot
launchctl stop com.alibot.whatsapp
launchctl stop com.alibot.facebook

# הפעלה
launchctl start com.alibot.bot
launchctl start com.alibot.whatsapp
launchctl start com.alibot.facebook

# Restart
launchctl stop com.alibot.bot && launchctl start com.alibot.bot
launchctl stop com.alibot.facebook && launchctl start com.alibot.facebook

# לוגים חיים
tail -f /tmp/alibot.log
tail -f /tmp/wa_service.log
tail -f /tmp/facebook_service.log

# בדיקת WhatsApp health
curl http://localhost:3001/health

# בדיקת Facebook health
curl http://127.0.0.1:3002/health
```

### עדכון קוד על המיני

מהמחשב הראשי:

```bash
# העתק קובץ ספציפי
scp path/to/file.py asafbenatia@10.0.0.26:~/Projects/alibot/path/to/file.py

# העתק הכל (זהירות — דורס קבצים)
scp -r /Users/asafbenatia/Projects/_personal/alibot/ asafbenatia@10.0.0.26:~/Projects/alibot/

# אחרי עדכון — restart
ssh asafbenatia@10.0.0.26 'launchctl stop com.alibot.bot && launchctl start com.alibot.bot'
```

### אם WhatsApp מתנתק

אם ה-WhatsApp service מאבד חיבור (בדרך כלל אחרי עדכון וואטסאפ בטלפון):

```bash
# על המיני:
launchctl stop com.alibot.whatsapp
rm -rf ~/Projects/alibot/whatsapp/auth_state    # מחק session ישן
launchctl start com.alibot.whatsapp
# בדוק ב-log את ה-QR ותסרוק מחדש:
tail -f /tmp/wa_service.log
```

### אם Telegram מתנתק

בדרך כלל Telethon מתחבר מחדש אוטומטית. אם לא:

```bash
ssh asafbenatia@10.0.0.26 'launchctl stop com.alibot.bot && launchctl start com.alibot.bot'
```

## Dashboard

נגיש מהרשת המקומית: **http://10.0.0.26:8080**

דפים:
- `/` — סטטיסטיקות, דילים אחרונים
- `/deals` — כל הדילים עם פילטרים
- `/deals/{id}` — פרטי דיל
- `/queue` — תור פרסום (דלג/קדם)
- `/settings` — הגדרות (קריאה בלבד)
- `/logs` — 100 שורות אחרונות מהלוג

## פקודות Admin (טלגרם)

שלח מהחשבון האישי שלך לחשבון הייעודי:

| פקודה | מה זה עושה |
|-------|------------|
| `/stats` | סטטיסטיקות היום |
| `/pause` | עצור פרסום (עיבוד ממשיך) |
| `/resume` | חדש פרסום |
| `/queue` | כמה דילים בתור |
| `/skip <id>` | דלג על דיל ספציפי |
| `/last` | 5 דילים אחרונים שפורסמו |

## AliExpress API

### IP Whitelist

ה-API דורש IP whitelist. אם הבוט עובר לרשת אחרת:

1. בדוק IP חדש: `curl https://api.ipify.org`
2. הוסף ב-portals.aliexpress.com → App Management → IP Whitelist

### Advanced API (ממתין לאישור)

הוגשה בקשה ל-`aliexpress.affiliate.hotproduct.query` ו-`smart_match_product`. כשיאושר, להוסיף כאסטרטגיה נוספת ב-`bot/hot_products.py`.

## שער דולר-שקל

הבוט מעדכן את שער הדולר-שקל אוטומטית:
- **בהפעלה** — שולף שער מיד
- **כל יום ב-08:00** — עדכון יומי

השער מועבר ל-AI rewriter, שמציג מחירים גם בדולר וגם בשקלים (למשל: "$2.99 (כ-₪9.15)").

API: `exchangerate-api.com` (חינם, ללא הרשמה).

## מוצרים חמים (Hot Products)

כל 4 שעות הבוט שולף אוטומטית מוצרים טרנדיים מ-AliExpress API ומפרסם אותם.

**3 אסטרטגיות ברוטציה:**
- **Best Sellers** — מוצרים עם הכי הרבה מכירות
- **High Commission** — מוצרים עם העמלה הכי גבוהה
- **Cheapest Deals** — מוצרים זולים (impulse buys)

**30 מילות חיפוש** מותאמות לקהל ישראלי (bluetooth earbuds, kitchen gadgets, phone case, וכו').

מוצרים חמים מסומנים ב-DB עם `source_group = "hot_products"`.

## Troubleshooting

### הבוט לא מפרסם

1. בדוק לוגים: `ssh asafbenatia@10.0.0.26 'tail -30 /tmp/alibot.log'`
2. בדוק rate limit: אולי הגיע למקסימום לשעה
3. בדוק quiet hours: 23:00-07:00 לא מפרסם
4. בדוק שה-service רץ: `launchctl list | grep alibot`
5. שלח `/stats` ו-`/queue` מטלגרם

### Caption too long

טלגרם מגביל caption של תמונה ל-1024 תווים. הקוד חותך אוטומטית, אבל אם ה-AI כותב ארוך מדי, הטקסט ייחתך עם `...`.

### WhatsApp לא שולח

1. בדוק health: `ssh asafbenatia@10.0.0.26 'curl http://localhost:3001/health'`
2. אם disconnected — ראה "אם WhatsApp מתנתק" למעלה
3. אם connected אבל לא שולח — בדוק `group_jid` ב-config.yaml

### AliExpress API — IP whitelist error

```
The binding IP whitelist of the app does not contain the source IP
```

הוסף את ה-IP של המיני ב-portals.aliexpress.com. בדוק IP:
```bash
ssh asafbenatia@10.0.0.26 'curl -s https://api.ipify.org'
```

## עלויות חודשיות

| פריט | עלות |
|------|------|
| OpenAI API (gpt-4o-mini) | ~$1-3 |
| AliExpress API | חינם |
| Telegram API | חינם |
| Mac mini (חשמל) | כבר רץ |
| **סה"כ** | **~$1-3/חודש** |
