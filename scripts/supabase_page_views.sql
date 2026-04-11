-- Page views counter for the website
-- Run this in the Supabase SQL Editor

CREATE TABLE page_views (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    path TEXT NOT NULL DEFAULT '/',
    views INTEGER NOT NULL DEFAULT 1,
    UNIQUE(date, path)
);

CREATE INDEX idx_page_views_date ON page_views(date DESC);

ALTER TABLE page_views ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow anonymous inserts" ON page_views
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow anonymous reads" ON page_views
    FOR SELECT USING (true);

CREATE POLICY "Allow anonymous updates" ON page_views
    FOR UPDATE USING (true);

-- Atomic increment function
CREATE OR REPLACE FUNCTION increment_page_view(view_date DATE, view_path TEXT)
RETURNS void AS $$
BEGIN
    INSERT INTO page_views (date, path, views)
    VALUES (view_date, view_path, 1)
    ON CONFLICT (date, path)
    DO UPDATE SET views = page_views.views + 1;
END;
$$ LANGUAGE plpgsql;
