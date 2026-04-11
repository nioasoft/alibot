-- AliBot Website: Supabase Migration
-- Run this in the Supabase SQL Editor after creating your project.

-- ============================================================
-- 1. Deals table (website-optimized, denormalized)
-- ============================================================
CREATE TABLE deals (
    id              BIGSERIAL PRIMARY KEY,
    product_id      TEXT UNIQUE NOT NULL,
    product_name    TEXT NOT NULL,
    rewritten_text  TEXT NOT NULL,
    price           NUMERIC(10, 2) NOT NULL,
    original_price  NUMERIC(10, 2),
    currency        TEXT NOT NULL DEFAULT 'USD',
    price_ils       NUMERIC(10, 2),
    category        TEXT NOT NULL DEFAULT 'other',
    affiliate_link  TEXT,
    product_link    TEXT NOT NULL,
    image_url       TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    published_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for website queries
CREATE INDEX idx_deals_category_published ON deals(category, published_at DESC);
CREATE INDEX idx_deals_active ON deals(is_active) WHERE is_active = TRUE;

-- ============================================================
-- 2. Row Level Security
-- ============================================================
ALTER TABLE deals ENABLE ROW LEVEL SECURITY;

-- Public read for the website (anon key) - only active deals
CREATE POLICY "Public can read active deals"
    ON deals FOR SELECT
    USING (is_active = TRUE);

-- Bot writes with service_role key (bypasses RLS automatically)

-- ============================================================
-- 3. Storage bucket for deal images
-- ============================================================
-- Create via Supabase Dashboard > Storage > New Bucket:
--   Name: deal-images
--   Public: YES
--   File size limit: 10MB
--   Allowed MIME types: image/jpeg, image/png, image/webp

-- ============================================================
-- 4. Auto-cleanup: delete deals older than 7 days
-- ============================================================
CREATE OR REPLACE FUNCTION cleanup_old_deals()
RETURNS void AS $$
BEGIN
    DELETE FROM deals
    WHERE published_at < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

-- Enable pg_cron extension (may already be enabled)
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Schedule daily cleanup at 04:00 UTC
SELECT cron.schedule(
    'cleanup-old-deals',
    '0 4 * * *',
    'SELECT cleanup_old_deals()'
);
