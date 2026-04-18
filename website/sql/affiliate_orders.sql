create extension if not exists pgcrypto;

create table if not exists public.affiliate_orders (
  id uuid primary key default gen_random_uuid(),
  order_key text not null unique,
  account_key text not null,
  order_id text not null,
  sub_order_id text,
  order_status text,
  tracking_id text,
  custom_parameters text,
  product_id text,
  product_title text,
  product_detail_url text,
  product_main_image_url text,
  product_count integer,
  ship_to_country text,
  settled_currency text,
  paid_amount numeric,
  finished_amount numeric,
  estimated_paid_commission numeric,
  estimated_finished_commission numeric,
  commission_rate numeric,
  incentive_commission_rate numeric,
  new_buyer_bonus_commission numeric,
  is_new_buyer boolean,
  order_type text,
  order_platform text,
  effect_detail_status text,
  category_id integer,
  resolved_category text,
  created_time timestamptz,
  paid_time timestamptz,
  finished_time timestamptz,
  completed_settlement_time timestamptz,
  raw_payload jsonb not null default '{}'::jsonb,
  synced_at timestamptz not null default timezone('utc', now()),
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists affiliate_orders_tracking_id_idx
  on public.affiliate_orders (tracking_id);

create index if not exists affiliate_orders_product_id_idx
  on public.affiliate_orders (product_id);

create index if not exists affiliate_orders_status_idx
  on public.affiliate_orders (order_status);

create index if not exists affiliate_orders_category_idx
  on public.affiliate_orders (resolved_category);

create index if not exists affiliate_orders_created_time_idx
  on public.affiliate_orders (created_time desc);

alter table public.affiliate_orders enable row level security;
revoke all on public.affiliate_orders from anon, authenticated;
