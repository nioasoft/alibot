# Affiliate Intelligence System Plan

## Goal

Build a measurable learning system that improves deal quality over time by combining:

- internal click tracking
- AliExpress affiliate order sync
- source-group reputation
- audience preference scoring
- category discovery for future dedicated groups

The system should help answer:

- Which source groups bring buyers instead of noise?
- Which deal patterns actually convert?
- Which categories deserve more exposure?
- When should we create a new dedicated destination group?

## Current Ground Truth

- The current bot already stores deals, queue items, source groups, affiliate links, and destinations.
- The installed AliExpress SDK supports affiliate order endpoints:
  - `aliexpress.affiliate.order.list`
  - `aliexpress.affiliate.order.get`
  - `aliexpress.affiliate.order.listbyindex`
- We have not confirmed a public click-report endpoint with the same confidence.
- Therefore, the reliable path is:
  - clicks measured by us
  - orders/conversions synced from AliExpress

## Success Criteria

After rollout, we should be able to:

1. attribute clicks to specific deals, posts, destinations, and source groups
2. attribute affiliate orders to tracking IDs and, when available, to internal custom parameters
3. score each source group by observed buyer value, not just message volume
4. rank incoming deals using both static quality and learned buyer preference
5. identify categories/subcategories worth splitting into dedicated groups

## System Principles

### 1. Learn from buyer behavior, not only product metadata

Orders, clicks, conversion rate, and revenue should influence promotion decisions.

### 2. Keep attribution explicit

Every outgoing affiliate link should carry enough metadata to reconstruct:

- deal
- queue item
- platform
- destination
- source group
- experiment variant

### 3. Separate observation from optimization

First collect correct data, then score, then automate decisions.

### 4. Keep explanations auditable

Every score or routing recommendation should be explainable from stored inputs.

## Phase Plan

## Phase 0: Validation and Instrumentation Contract

### Objective

Lock down the attribution model before building storage and automation.

### Deliverables

- documented AliExpress order sync contract
- documented custom parameter format
- documented tracking ID strategy

### Tasks

- verify production response shape for `get_order_list` and `get_order_get`
- inspect which fields are always present:
  - `tracking_id`
  - `custom_parameters`
  - `product_id`
  - `product_title`
  - `paid_amount`
  - `commission_rate`
  - `order_status`
- define a compact `custom_parameters` payload format
- define tracking IDs by channel family, not just by account

### Recommended Tracking Strategy

- one AliExpress tracking ID per major distribution lane:
  - `tg_main`
  - `wa_main`
  - `fb_main`
  - `wa_tech`
  - future dedicated lanes

### Recommended Custom Parameters Payload

Short key-value payload, for example:

`d=123;q=456;dst=wa_main;src=DesignYourHome;pf=wa;v=a`

If AliExpress length limits are tight, store a compact token instead:

`atk=abc123xyz`

where `atk` maps back to full metadata in our DB.

## Phase 1: Click Tracking Foundation

### Objective

Measure all outgoing affiliate clicks inside our own system.

### Why

Even if AliExpress exposes click stats in the dashboard, we need first-party click data tied to our exact internal entities.

### Deliverables

- redirect endpoint
- click event storage
- link token generation
- publisher integration

### Proposed Components

- `bot/link_tracking.py`
- `dashboard/app.py` or new route handler for redirect
- publisher changes for Telegram / WhatsApp / Facebook

### Proposed Data Model

#### `affiliate_link_tokens`

- `id`
- `token` unique
- `deal_id`
- `queue_item_id`
- `destination_key`
- `platform`
- `source_group`
- `affiliate_account_key`
- `tracking_id`
- `custom_parameters`
- `target_url`
- `created_at`

#### `affiliate_click_events`

- `id`
- `token`
- `deal_id`
- `queue_item_id`
- `destination_key`
- `platform`
- `source_group`
- `clicked_at`
- `user_agent`
- `referer`
- `ip_hash`

### Flow

1. publisher generates tracked URL like `/go/<token>`
2. user clicks tracked URL
3. we log click event
4. we issue `302` redirect to AliExpress affiliate URL

## Phase 2: AliExpress Order Sync

### Objective

Import affiliate order data from AliExpress on a schedule.

### Deliverables

- order sync service
- normalized order tables
- incremental sync cursor
- reconciliation logic

### Proposed Components

- `bot/affiliate_reporting.py`
- scheduled job in `main.py`
- dashboard views for performance

### Proposed Data Model

#### `affiliate_orders`

- `id`
- `external_order_id`
- `external_sub_order_id`
- `tracking_id`
- `custom_parameters`
- `product_id`
- `product_title`
- `order_status`
- `effect_detail_status`
- `paid_amount`
- `finished_amount`
- `estimated_paid_commission`
- `estimated_finished_commission`
- `commission_rate`
- `ship_to_country`
- `created_time`
- `paid_time`
- `finished_time`
- `synced_at`
- unique constraint on best external order identity

#### `affiliate_order_sync_runs`

- `id`
- `started_at`
- `finished_at`
- `status`
- `window_start`
- `window_end`
- `rows_inserted`
- `rows_updated`
- `error_message`

### Sync Strategy

- initial sync by date window
- ongoing incremental sync every 1-3 hours
- periodic reconciliation for the last 30-60 days because statuses mature over time
- use `listbyindex` for scalable backfills if needed

## Phase 3: Attribution Layer

### Objective

Map clicks and orders back to internal publishing decisions.

### Deliverables

- attribution resolver
- confidence labels
- performance rollups by entity

### Attribution Sources

#### Primary

- `custom_parameters` token or compact metadata

#### Secondary

- `tracking_id`

#### Tertiary

- `product_id` + time proximity + destination lane

### Attribution Confidence

- `exact`
- `lane_match`
- `heuristic`
- `unattributed`

### Proposed Rollup Tables

#### `deal_performance`

- `deal_id`
- `clicks`
- `orders`
- `revenue_paid_amount`
- `commission_estimated`
- `last_updated_at`

#### `source_group_performance`

- `source_group`
- `deals_seen`
- `deals_accepted`
- `deals_published`
- `clicks`
- `orders`
- `revenue_paid_amount`
- `commission_estimated`
- `acceptance_rate`
- `ctr`
- `conversion_rate`
- `revenue_per_100_deals`
- `last_updated_at`

#### `destination_performance`

- `destination_key`
- `clicks`
- `orders`
- `ctr`
- `conversion_rate`
- `revenue_paid_amount`

## Phase 4: Reputation and Preference Scoring

### Objective

Replace flat deal filtering with a learned scoring model.

### Score Layers

#### Base Quality Score

Existing signals from current `QualityGate`:

- orders count
- rating
- discount
- image availability
- affiliate readiness
- category confidence

#### Source Reputation Score

Signals:

- acceptance rate after filtering
- clicks per published deal
- orders per published deal
- revenue per published deal
- rolling 7/30 day performance

#### Audience Preference Score

Signals:

- clicks and orders by category
- clicks and orders by ali category
- clicks and orders by brand or keyword pattern
- price band performance
- shipping-tag performance
- coupon/promo presence performance

#### Saturation / Fatigue Penalty

Signals:

- too many similar items in short period
- same category overexposed
- same brand overexposed

### Proposed Final Score

`final_score = base_quality + source_reputation + audience_preference - saturation_penalty`

### Decision Outputs

- reject
- publish normally
- publish high priority
- publish only to selected lanes
- hold for manual review later if we add review queue

## Phase 5: Adaptive Routing and Category Discovery

### Objective

Learn when to create dedicated groups and route deals more precisely.

### Deliverables

- category opportunity report
- routing recommendations
- thresholds for new destination creation

### Examples

- kids toys
- kitchen gadgets
- beauty devices
- car accessories
- smart home

### Category Discovery Logic

A category or subcategory becomes a candidate for a dedicated group when it shows:

- sustained click volume
- sustained order volume
- above-average revenue per post
- enough inventory flow from multiple source groups

### Proposed Table

#### `audience_segment_candidates`

- `segment_key`
- `display_name`
- `basis_type`
- `basis_value`
- `clicks_30d`
- `orders_30d`
- `revenue_30d`
- `posts_30d`
- `candidate_score`
- `recommended_action`

## Phase 6: Dashboard and Operational Reporting

### Objective

Make the system inspectable and actionable without querying SQLite manually.

### Deliverables

- source performance dashboard
- deal performance dashboard
- order sync status dashboard
- category opportunity dashboard

### Dashboard Views

- top source groups by revenue
- worst source groups by noise ratio
- top categories by clicks
- top categories by orders
- top destinations by conversion
- unattributed orders report
- stale tracking IDs / broken attribution report

## Phase 7: Documentation and Decision Log

### Objective

Keep the system maintainable and explainable.

### Required Documentation

#### Technical docs

- architecture overview
- schema reference
- sync job behavior
- attribution rules
- scoring formula definitions
- failure modes and recovery

#### Operating docs

- how to add a new tracking ID
- how to add a new destination lane
- how to backfill order history
- how to verify attribution
- how to interpret dashboards

#### Product docs

- what counts as a "good source"
- what counts as a "candidate segment"
- when to create a new dedicated group
- when to retire a source group

### Documentation Location

- specs in `docs/superpowers/specs/`
- implementation plans in `docs/superpowers/plans/`
- operational runbooks in `README.md` plus dedicated docs as needed

## Initial File Plan

### New files

- `bot/affiliate_reporting.py`
- `bot/link_tracking.py`
- `tests/test_affiliate_reporting.py`
- `tests/test_link_tracking.py`
- `docs/superpowers/specs/2026-04-18-affiliate-intelligence-design.md`

### Files to extend

- `bot/models.py`
- `bot/publisher.py`
- `bot/telegram_publisher.py`
- `bot/whatsapp_publisher.py`
- `bot/facebook_publisher.py`
- `bot/quality.py`
- `bot/pipeline.py`
- `dashboard/routes.py`
- `dashboard/templates/index.html`
- `dashboard/templates/deals.html`
- `dashboard/templates/deal_detail.html`
- `main.py`
- `README.md`

## Implementation Order

1. Phase 0 validation helpers
2. Phase 1 click tracking
3. Phase 2 order sync
4. Phase 3 attribution
5. Phase 4 learned scoring
6. Phase 6 dashboards
7. Phase 5 adaptive routing
8. Phase 7 final docs pass

This order is intentional:

- no learning before measurement
- no routing changes before attribution
- no automation before visibility

## Risk Register

### Risk: AliExpress `custom_parameters` may be absent or inconsistent

Mitigation:

- keep per-lane `tracking_id`
- log exact raw order payloads
- build confidence-based attribution

### Risk: clicks API may not be publicly available

Mitigation:

- treat first-party click tracking as canonical

### Risk: delayed order maturation

Mitigation:

- reconcile recent windows repeatedly
- separate estimated commission from finished commission

### Risk: overfitting to short-term spikes

Mitigation:

- use rolling 7/30 day windows
- require minimum sample size before boosting segments

### Risk: too much automation creates bad routing decisions

Mitigation:

- first surface recommendations
- only automate after review of real data

## Milestone Definition

### Milestone A

We can answer:

- which posts got clicked
- which lanes get the most clicks

### Milestone B

We can answer:

- which affiliate orders came in
- which tracking IDs convert

### Milestone C

We can answer:

- which source groups produce buyers
- which categories deserve more supply

### Milestone D

We can answer:

- which segment deserves its own dedicated group
- how to reroute future deals automatically

