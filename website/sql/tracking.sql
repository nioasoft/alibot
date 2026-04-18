create extension if not exists pgcrypto;

create table if not exists public.tracking_links (
  id uuid primary key default gen_random_uuid(),
  token text not null unique,
  idempotency_key text not null unique,
  target_url text not null,
  deal_id bigint,
  queue_item_id bigint,
  platform text,
  destination_key text,
  source_group text,
  post_variant text,
  metadata jsonb not null default '{}'::jsonb,
  click_count bigint not null default 0,
  last_clicked_at timestamptz,
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists tracking_links_queue_item_idx
  on public.tracking_links (queue_item_id);

create index if not exists tracking_links_destination_idx
  on public.tracking_links (platform, destination_key);

create table if not exists public.tracking_click_events (
  id uuid primary key default gen_random_uuid(),
  tracking_link_id uuid not null references public.tracking_links(id) on delete cascade,
  token text not null,
  clicked_at timestamptz not null default timezone('utc', now()),
  ip_hash text,
  user_agent text,
  referer text,
  country_code text,
  cf_ray text
);

create index if not exists tracking_click_events_link_idx
  on public.tracking_click_events (tracking_link_id, clicked_at desc);

create index if not exists tracking_click_events_token_idx
  on public.tracking_click_events (token, clicked_at desc);

alter table public.tracking_links enable row level security;
alter table public.tracking_click_events enable row level security;

create or replace function public.increment_tracking_link_clicks(
  link_id uuid,
  clicked_at timestamptz
)
returns void
language sql
security definer
set search_path = public
as $$
  update public.tracking_links
  set
    click_count = click_count + 1,
    last_clicked_at = clicked_at
  where id = link_id;
$$;

revoke all on public.tracking_links from anon, authenticated;
revoke all on public.tracking_click_events from anon, authenticated;
revoke all on function public.increment_tracking_link_clicks(uuid, timestamptz) from anon, authenticated;
