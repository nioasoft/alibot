import { getSupabaseAdmin } from "@/lib/supabase-admin";

export interface TrackingSummary {
  totalLinks: number;
  totalClicks: number;
  clickedLinks: number;
  lastClickAt: string | null;
}

export interface OrderSummary {
  totalOrders: number;
  paymentCompletedOrders: number;
  buyerConfirmedOrders: number;
  estimatedPaidCommission: number;
  estimatedFinishedCommission: number;
}

export interface TrackingLinkRow {
  token: string;
  targetUrl: string;
  platform: string | null;
  destinationKey: string | null;
  sourceGroup: string | null;
  category: string | null;
  clickCount: number;
  createdAt: string;
  lastClickedAt: string | null;
}

export interface TrackingCategoryRow {
  category: string;
  links: number;
  clicks: number;
}

export interface OrderCategoryRow {
  category: string;
  orders: number;
  estimatedFinishedCommission: number;
}

export interface TrackingClickRow {
  token: string;
  clickedAt: string;
  countryCode: string | null;
  referer: string | null;
  platform: string | null;
  destinationKey: string | null;
  sourceGroup: string | null;
  category: string | null;
}

export interface AffiliateOrderRow {
  accountKey: string;
  orderId: string;
  orderStatus: string | null;
  productId: string | null;
  productTitle: string | null;
  resolvedCategory: string | null;
  trackingId: string | null;
  estimatedPaidCommission: number;
  estimatedFinishedCommission: number;
  createdTime: string | null;
  finishedTime: string | null;
}

export async function getTrackingDashboardData() {
  const supabase = getSupabaseAdmin();

  const [
    totalLinksResult,
    totalClicksResult,
    clickedLinksResult,
    lastClickResult,
    topLinksResult,
    recentLinksResult,
    categoryLinksResult,
    recentClicksResult,
    orderCountResult,
    paymentCompletedCountResult,
    buyerConfirmedCountResult,
    orderStatsRowsResult,
    recentOrdersResult,
  ] = await Promise.all([
    supabase
      .from("tracking_links")
      .select("id", { count: "exact", head: true }),
    supabase
      .from("tracking_click_events")
      .select("id", { count: "exact", head: true }),
    supabase
      .from("tracking_links")
      .select("id", { count: "exact", head: true })
      .gt("click_count", 0),
    supabase
      .from("tracking_links")
      .select("last_clicked_at")
      .not("last_clicked_at", "is", null)
      .order("last_clicked_at", { ascending: false })
      .limit(1)
      .maybeSingle(),
    supabase
      .from("tracking_links")
      .select(
        "token, target_url, platform, destination_key, source_group, click_count, created_at, last_clicked_at, metadata"
      )
      .order("click_count", { ascending: false })
      .order("created_at", { ascending: false })
      .limit(10),
    supabase
      .from("tracking_links")
      .select(
        "token, target_url, platform, destination_key, source_group, click_count, created_at, last_clicked_at, metadata"
      )
      .order("created_at", { ascending: false })
      .limit(25),
    supabase
      .from("tracking_links")
      .select("click_count, metadata")
      .order("created_at", { ascending: false })
      .limit(1000),
    supabase
      .from("tracking_click_events")
      .select(
        "token, clicked_at, country_code, referer, tracking_links(platform, destination_key, source_group, metadata)"
      )
      .order("clicked_at", { ascending: false })
      .limit(25),
    supabase
      .from("affiliate_orders")
      .select("id", { count: "exact", head: true }),
    supabase
      .from("affiliate_orders")
      .select("id", { count: "exact", head: true })
      .eq("order_status", "Payment Completed"),
    supabase
      .from("affiliate_orders")
      .select("id", { count: "exact", head: true })
      .eq("order_status", "Buyer Confirmed Receipt"),
    supabase
      .from("affiliate_orders")
      .select(
        "resolved_category, estimated_paid_commission, estimated_finished_commission"
      )
      .order("created_time", { ascending: false })
      .limit(5000),
    supabase
      .from("affiliate_orders")
      .select(
        "account_key, order_id, order_status, product_id, product_title, resolved_category, tracking_id, estimated_paid_commission, estimated_finished_commission, created_time, finished_time"
      )
      .order("created_time", { ascending: false })
      .limit(25),
  ]);

  throwIfError(totalLinksResult.error);
  throwIfError(totalClicksResult.error);
  throwIfError(clickedLinksResult.error);
  throwIfError(lastClickResult.error);
  throwIfError(topLinksResult.error);
  throwIfError(recentLinksResult.error);
  throwIfError(categoryLinksResult.error);
  throwIfError(recentClicksResult.error);
  throwIfError(orderCountResult.error);
  throwIfError(paymentCompletedCountResult.error);
  throwIfError(buyerConfirmedCountResult.error);
  throwIfError(orderStatsRowsResult.error);
  throwIfError(recentOrdersResult.error);

  const categoryStats = buildCategoryStats(categoryLinksResult.data ?? []);
  const orderStats = buildOrderStats(orderStatsRowsResult.data ?? []);
  const orderCategoryStats = buildOrderCategoryStats(orderStatsRowsResult.data ?? []);

  return {
    summary: {
      totalLinks: totalLinksResult.count ?? 0,
      totalClicks: totalClicksResult.count ?? 0,
      clickedLinks: clickedLinksResult.count ?? 0,
      lastClickAt: lastClickResult.data?.last_clicked_at ?? null,
    } satisfies TrackingSummary,
    orderSummary: {
      totalOrders: orderCountResult.count ?? 0,
      paymentCompletedOrders: paymentCompletedCountResult.count ?? 0,
      buyerConfirmedOrders: buyerConfirmedCountResult.count ?? 0,
      estimatedPaidCommission: orderStats.estimatedPaidCommission,
      estimatedFinishedCommission: orderStats.estimatedFinishedCommission,
    } satisfies OrderSummary,
    categoryStats,
    orderCategoryStats,
    topLinks: (topLinksResult.data ?? []).map(mapLinkRow),
    recentLinks: (recentLinksResult.data ?? []).map(mapLinkRow),
    recentClicks: (recentClicksResult.data ?? []).map(mapClickRow),
    recentOrders: (recentOrdersResult.data ?? []).map(mapOrderRow),
  };
}

function mapLinkRow(row: Record<string, unknown>): TrackingLinkRow {
  return {
    token: toStringValue(row.token) ?? "",
    targetUrl: toStringValue(row.target_url) ?? "",
    platform: toStringValue(row.platform),
    destinationKey: toStringValue(row.destination_key),
    sourceGroup: toStringValue(row.source_group),
    category: extractCategory(row.metadata),
    clickCount: toNumberValue(row.click_count),
    createdAt: toStringValue(row.created_at) ?? "",
    lastClickedAt: toStringValue(row.last_clicked_at),
  };
}

function mapClickRow(row: Record<string, unknown>): TrackingClickRow {
  const link = extractLinkedTrackingRow(row.tracking_links);

  return {
    token: toStringValue(row.token) ?? "",
    clickedAt: toStringValue(row.clicked_at) ?? "",
    countryCode: toStringValue(row.country_code),
    referer: toStringValue(row.referer),
    platform: toStringValue(link.platform),
    destinationKey: toStringValue(link.destination_key),
    sourceGroup: toStringValue(link.source_group),
    category: extractCategory(link.metadata),
  };
}

function mapOrderRow(row: Record<string, unknown>): AffiliateOrderRow {
  return {
    accountKey: toStringValue(row.account_key) ?? "",
    orderId: toStringValue(row.order_id) ?? "",
    orderStatus: toStringValue(row.order_status),
    productId: toStringValue(row.product_id),
    productTitle: toStringValue(row.product_title),
    resolvedCategory: toStringValue(row.resolved_category),
    trackingId: toStringValue(row.tracking_id),
    estimatedPaidCommission: toNumberValue(row.estimated_paid_commission),
    estimatedFinishedCommission: toNumberValue(row.estimated_finished_commission),
    createdTime: toStringValue(row.created_time),
    finishedTime: toStringValue(row.finished_time),
  };
}

function buildCategoryStats(rows: unknown[]): TrackingCategoryRow[] {
  const byCategory = new Map<string, TrackingCategoryRow>();

  for (const row of rows) {
    const record =
      row && typeof row === "object" ? (row as Record<string, unknown>) : {};
    const category = extractCategory(record.metadata) ?? "other";
    const existing = byCategory.get(category) ?? {
      category,
      links: 0,
      clicks: 0,
    };
    existing.links += 1;
    existing.clicks += toNumberValue(record.click_count);
    byCategory.set(category, existing);
  }

  return [...byCategory.values()].sort((left, right) => {
    if (right.clicks !== left.clicks) {
      return right.clicks - left.clicks;
    }
    return right.links - left.links;
  });
}

function buildOrderStats(rows: unknown[]) {
  let estimatedPaidCommission = 0;
  let estimatedFinishedCommission = 0;

  for (const row of rows) {
    const record =
      row && typeof row === "object" ? (row as Record<string, unknown>) : {};
    estimatedPaidCommission += toNumberValue(record.estimated_paid_commission);
    estimatedFinishedCommission += toNumberValue(record.estimated_finished_commission);
  }

  return {
    estimatedPaidCommission,
    estimatedFinishedCommission,
  };
}

function buildOrderCategoryStats(rows: unknown[]): OrderCategoryRow[] {
  const byCategory = new Map<string, OrderCategoryRow>();

  for (const row of rows) {
    const record =
      row && typeof row === "object" ? (row as Record<string, unknown>) : {};
    const category = toStringValue(record.resolved_category) ?? "other";
    const existing = byCategory.get(category) ?? {
      category,
      orders: 0,
      estimatedFinishedCommission: 0,
    };
    existing.orders += 1;
    existing.estimatedFinishedCommission += toNumberValue(
      record.estimated_finished_commission
    );
    byCategory.set(category, existing);
  }

  return [...byCategory.values()].sort((left, right) => {
    if (right.estimatedFinishedCommission !== left.estimatedFinishedCommission) {
      return right.estimatedFinishedCommission - left.estimatedFinishedCommission;
    }
    return right.orders - left.orders;
  });
}

function extractLinkedTrackingRow(value: unknown): Record<string, unknown> {
  if (Array.isArray(value)) {
    const [first] = value;
    return first && typeof first === "object"
      ? (first as Record<string, unknown>)
      : {};
  }

  return value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
}

function extractCategory(value: unknown): string | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }

  return toStringValue((value as Record<string, unknown>).category);
}

function toStringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function toNumberValue(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }

  return 0;
}

function throwIfError(error: { message?: string } | null) {
  if (error) {
    throw new Error(error.message ?? "Supabase query failed");
  }
}
