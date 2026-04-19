# Facebook Group POC

This is a standalone Playwright service for posting a single deal to a Facebook group using an existing logged-in profile.

## Scope

- One Facebook profile
- One or more group URLs
- Text post
- Optional image upload
- Local session storage via Playwright `storageState`
- No bot integration yet

## Setup

```bash
cd facebook
cp .env.example .env
npm install
npx playwright install chromium
```

## Save Session

Run the auth flow once:

```bash
npm run auth
```

This opens Chromium. Log into Facebook manually, open the target group to confirm access, then return to the terminal and press Enter. The session is saved to `.auth/facebook.json`.

If you keep Facebook credentials in env vars, the auth flow can also log in automatically.
Supported names:

```bash
FB_LOGIN_EMAIL=...
FB_LOGIN_PASSWORD=...
```

For compatibility with the main repo `.env`, the service also accepts:

```bash
USERNAME=...
PASSWORD=...
```

If Facebook should always re-authenticate against a specific group or deals page, set:

```bash
FB_AUTH_TARGET_URL=https://www.facebook.com/groups/your-group-or-deals-url
```

That makes both `npm run auth` and `POST /refresh-auth` land on the exact page that publishing uses, instead of only logging into the generic Facebook home page.

## Test Post

```bash
npm run post:test -- --text "בדיקת פוסט" --dry-run
npm run post:test -- --text "בדיקת פוסט אמיתית" --image ../data/images/example.jpg
npm run post:test -- --text "טקסט עם לינק ראשון" --append-text "\n\n🌐 להצטרפות לכל הקבוצות: https://www.dilim.net/" --dry-run
```

`--dry-run` reaches the publish dialog, fills the content, and stops before clicking `Post`.
By default it waits 5 seconds before the screenshot so Facebook link previews can load.

## Local HTTP Bridge

```bash
npm start
```

Endpoints:

- `GET /health`
- `POST /publish`
- `POST /refresh-auth`

Example payload:

```json
{
  "group_url": "https://www.facebook.com/groups/your-group",
  "text": "Deal text here",
  "image_path": "/absolute/path/to/image.jpg",
  "dry_run": true
}
```

`POST /refresh-auth` also accepts `group_url`, so you can refresh the saved session directly against the exact group/deals page that should be used for publishing.

## Notes

- Facebook UI changes frequently. Expect selector tuning during the first live run.
- Keep this isolated from the main bot until we prove the flow is stable.
- Use a dedicated Facebook profile for automation.
