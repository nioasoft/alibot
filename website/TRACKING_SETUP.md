# Tracking Setup

This website project can host the public deal tracker on the same Vercel app.

## Routes

- `POST /api/tracking-links`
  - Internal endpoint for the bot.
  - Requires `x-tracking-secret`.
  - Creates or reuses a token by `idempotencyKey`.
- `GET /go/[token]`
  - Public redirect endpoint.
  - Records the click in Supabase.
  - Returns `302` to the stored AliExpress URL.

## Required Environment Variables

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `TRACKING_API_SECRET`
- `TRACKING_BASE_URL`

## Recommended Environment Variables

- `TRACKING_IP_HASH_SALT`

If `TRACKING_IP_HASH_SALT` is omitted, the tracker will skip IP hashing and store no IP-derived fingerprint.

## Supabase Setup

Run [tracking.sql](/Users/asafbenatia/Projects/_personal/alibot/website/sql/tracking.sql:1) in the Supabase SQL editor.

## Bot Request Shape

`POST /api/tracking-links`

```json
{
  "idempotencyKey": "queue-128:telegram:tg_main",
  "targetUrl": "https://s.click.aliexpress.com/e/_example",
  "dealId": 128,
  "queueItemId": 991,
  "platform": "telegram",
  "destinationKey": "tg_main",
  "sourceGroup": "@topdealshub",
  "postVariant": "default",
  "metadata": {
    "category": "tech"
  }
}
```

Example response:

```json
{
  "token": "abc123token",
  "trackedUrl": "https://trk.dilim.net/go/abc123token",
  "reused": false
}
```

## Cloudflare / Vercel

- Point `trk.dilim.net` to the same Vercel project as the landing page.
- Set `TRACKING_BASE_URL=https://trk.dilim.net`.
- Keep the public redirect path on the tracker hostname: `https://trk.dilim.net/go/<token>`.
