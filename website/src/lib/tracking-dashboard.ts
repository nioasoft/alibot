import { getSupabaseAdmin } from "@/lib/supabase-admin";

export interface TrackingSummary {
  totalLinks: number;
  totalClicks: number;
  clickedLinks: number;
  lastClickAt: string | null;
}

export interface OrderSummary {
  totalOrders: number;
  attributedOrders: number;
  unattributedOrders: number;
  paymentCompletedOrders: number;
  buyerConfirmedOrders: number;
  estimatedPaidCommission: number;
  estimatedFinishedCommission: number;
  attributedFinishedCommission: number;
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
  links: number;
  clicks: number;
  orders: number;
  estimatedFinishedCommission: number;
  score: number;
}

export interface SourcePerformanceRow {
  sourceGroup: string;
  primaryCategory: string | null;
  links: number;
  clicks: number;
  clickedLinks: number;
  avgClicksPerLink: number;
  clickCoverageRate: number;
  score: number;
}

export interface RecommendationRow {
  kind: "promote_source" | "review_source" | "promote_category" | "investigate_category";
  title: string;
  detail: string;
  score: number;
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
  isAttributed: boolean;
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
    sourceLinksResult,
    recentClicksResult,
    orderCountResult,
    attributedOrderCountResult,
    unattributedOrderCountResult,
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
      .from("tracking_links")
      .select("source_group, click_count, metadata")
      .order("created_at", { ascending: false })
      .limit(5000),
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
      .not("resolved_category", "is", null),
    supabase
      .from("affiliate_orders")
      .select("id", { count: "exact", head: true })
      .is("resolved_category", null),
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
  throwIfError(sourceLinksResult.error);
  throwIfError(recentClicksResult.error);
  throwIfError(orderCountResult.error);
  throwIfError(attributedOrderCountResult.error);
  throwIfError(unattributedOrderCountResult.error);
  throwIfError(paymentCompletedCountResult.error);
  throwIfError(buyerConfirmedCountResult.error);
  throwIfError(orderStatsRowsResult.error);
  throwIfError(recentOrdersResult.error);

  const categoryStats = buildCategoryStats(categoryLinksResult.data ?? []);
  const orderStats = buildOrderStats(orderStatsRowsResult.data ?? []);
  const orderCategoryStats = buildOrderCategoryStats(
    orderStatsRowsResult.data ?? [],
    categoryLinksResult.data ?? []
  );
  const sourceStats = buildSourceStats(sourceLinksResult.data ?? []);
  const topSources = [...sourceStats]
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }
      return right.clicks - left.clicks;
    })
    .slice(0, 8);
  const weakestSources = [...sourceStats]
    .filter((row) => row.links >= 2)
    .sort((left, right) => {
      if (left.score !== right.score) {
        return left.score - right.score;
      }
      return right.links - left.links;
    })
    .slice(0, 8);
  const recommendations = buildRecommendations(sourceStats, orderCategoryStats);

  return {
    summary: {
      totalLinks: totalLinksResult.count ?? 0,
      totalClicks: totalClicksResult.count ?? 0,
      clickedLinks: clickedLinksResult.count ?? 0,
      lastClickAt: lastClickResult.data?.last_clicked_at ?? null,
    } satisfies TrackingSummary,
    orderSummary: {
      totalOrders: orderCountResult.count ?? 0,
      attributedOrders: attributedOrderCountResult.count ?? 0,
      unattributedOrders: unattributedOrderCountResult.count ?? 0,
      paymentCompletedOrders: paymentCompletedCountResult.count ?? 0,
      buyerConfirmedOrders: buyerConfirmedCountResult.count ?? 0,
      estimatedPaidCommission: orderStats.estimatedPaidCommission,
      estimatedFinishedCommission: orderStats.estimatedFinishedCommission,
      attributedFinishedCommission: orderStats.attributedFinishedCommission,
    } satisfies OrderSummary,
    categoryStats,
    orderCategoryStats,
    topSources,
    weakestSources,
    recommendations,
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
    isAttributed: Boolean(toStringValue(row.resolved_category)),
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
  let attributedFinishedCommission = 0;

  for (const row of rows) {
    const record =
      row && typeof row === "object" ? (row as Record<string, unknown>) : {};
    estimatedPaidCommission += toNumberValue(record.estimated_paid_commission);
    estimatedFinishedCommission += toNumberValue(record.estimated_finished_commission);
    if (toStringValue(record.resolved_category)) {
      attributedFinishedCommission += toNumberValue(record.estimated_finished_commission);
    }
  }

  return {
    estimatedPaidCommission,
    estimatedFinishedCommission,
    attributedFinishedCommission,
  };
}

function buildOrderCategoryStats(
  orderRows: unknown[],
  linkRows: unknown[]
): OrderCategoryRow[] {
  const byCategory = new Map<string, OrderCategoryRow>();

  for (const row of linkRows) {
    const record =
      row && typeof row === "object" ? (row as Record<string, unknown>) : {};
    const category = extractCategory(record.metadata) ?? "other";
    const existing = byCategory.get(category) ?? {
      category,
      links: 0,
      clicks: 0,
      orders: 0,
      estimatedFinishedCommission: 0,
      score: 0,
    };
    existing.links += 1;
    existing.clicks += toNumberValue(record.click_count);
    byCategory.set(category, existing);
  }

  for (const row of orderRows) {
    const record =
      row && typeof row === "object" ? (row as Record<string, unknown>) : {};
    const category = toStringValue(record.resolved_category);
    if (!category) {
      continue;
    }
    const existing = byCategory.get(category) ?? {
      category,
      links: 0,
      clicks: 0,
      orders: 0,
      estimatedFinishedCommission: 0,
      score: 0,
    };
    existing.orders += 1;
    existing.estimatedFinishedCommission += toNumberValue(
      record.estimated_finished_commission
    );
    byCategory.set(category, existing);
  }

  const rows = [...byCategory.values()].map((row) => ({
    ...row,
    score: scoreCategory(row),
  }));

  return rows.sort((left, right) => {
    if (right.score !== left.score) {
      return right.score - left.score;
    }
    if (right.estimatedFinishedCommission !== left.estimatedFinishedCommission) {
      return right.estimatedFinishedCommission - left.estimatedFinishedCommission;
    }
    return right.orders - left.orders;
  });
}

function buildSourceStats(rows: unknown[]): SourcePerformanceRow[] {
  const bySource = new Map<
    string,
    SourcePerformanceRow & { categoryCounts: Map<string, number> }
  >();

  for (const row of rows) {
    const record =
      row && typeof row === "object" ? (row as Record<string, unknown>) : {};
    const sourceGroup = toStringValue(record.source_group) ?? "unknown";
    const category = extractCategory(record.metadata) ?? "other";
    const clicks = toNumberValue(record.click_count);
    const existing = bySource.get(sourceGroup) ?? {
      sourceGroup,
      primaryCategory: null,
      links: 0,
      clicks: 0,
      clickedLinks: 0,
      avgClicksPerLink: 0,
      clickCoverageRate: 0,
      score: 0,
      categoryCounts: new Map<string, number>(),
    };

    existing.links += 1;
    existing.clicks += clicks;
    if (clicks > 0) {
      existing.clickedLinks += 1;
    }
    existing.categoryCounts.set(category, (existing.categoryCounts.get(category) ?? 0) + 1);
    bySource.set(sourceGroup, existing);
  }

  return [...bySource.values()].map((row) => {
    const primaryCategory = [...row.categoryCounts.entries()].sort((left, right) => {
      if (right[1] !== left[1]) {
        return right[1] - left[1];
      }
      return left[0].localeCompare(right[0]);
    })[0]?.[0] ?? null;
    const avgClicksPerLink = row.links ? row.clicks / row.links : 0;
    const clickCoverageRate = row.links ? row.clickedLinks / row.links : 0;
    const score = scoreSource(avgClicksPerLink, clickCoverageRate, row.links, row.clicks);
    return {
      sourceGroup: row.sourceGroup,
      primaryCategory,
      links: row.links,
      clicks: row.clicks,
      clickedLinks: row.clickedLinks,
      avgClicksPerLink,
      clickCoverageRate,
      score,
    };
  });
}

function buildRecommendations(
  sources: SourcePerformanceRow[],
  categories: OrderCategoryRow[]
): RecommendationRow[] {
  const recommendations: RecommendationRow[] = [];

  for (const source of sources) {
    if (source.links >= 3 && source.score >= 60) {
      recommendations.push({
        kind: "promote_source",
        title: `לתגבר את ${source.sourceGroup}`,
        detail: `המקור הזה מייצר ${source.clicks} קליקים על ${source.links} לינקים, בעיקר בקטגוריית ${source.primaryCategory ?? "other"}.`,
        score: source.score,
      });
    } else if (source.links >= 3 && source.clicks === 0) {
      recommendations.push({
        kind: "review_source",
        title: `לבדוק אם להחליש את ${source.sourceGroup}`,
        detail: `המקור הזה ייצר ${source.links} לינקים בלי אפילו קליק אחד.`,
        score: 100 - source.score,
      });
    }
  }

  for (const category of categories) {
    if (category.orders >= 2 || category.estimatedFinishedCommission >= 3) {
      recommendations.push({
        kind: "promote_category",
        title: `לשקול לחזק את קטגוריית ${category.category}`,
        detail: `הקטגוריה ייצרה ${category.clicks} קליקים, ${category.orders} הזמנות ועמלה משוערת של $${category.estimatedFinishedCommission.toFixed(2)}.`,
        score: category.score,
      });
    } else if (category.links >= 4 && category.clicks >= 4 && category.orders === 0) {
      recommendations.push({
        kind: "investigate_category",
        title: `לבדוק למה ${category.category} לא ממירה`,
        detail: `יש עניין ראשוני בקטגוריה עם ${category.clicks} קליקים על ${category.links} לינקים, אבל עדיין אין הזמנות משויכות.`,
        score: category.score,
      });
    }
  }

  return recommendations
    .sort((left, right) => right.score - left.score)
    .slice(0, 8);
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

function scoreSource(
  avgClicksPerLink: number,
  clickCoverageRate: number,
  links: number,
  clicks: number
): number {
  const rawScore =
    avgClicksPerLink * 24 +
    clickCoverageRate * 42 +
    Math.min(links, 12) +
    Math.min(clicks, 10) * 2;
  return Math.max(0, Math.min(100, Math.round(rawScore)));
}

function scoreCategory(row: OrderCategoryRow): number {
  const rawScore =
    row.clicks * 4 +
    row.orders * 18 +
    row.estimatedFinishedCommission * 3 +
    Math.min(row.links, 10);
  return Math.max(0, Math.min(100, Math.round(rawScore)));
}

function throwIfError(error: { message?: string } | null) {
  if (error) {
    throw new Error(error.message ?? "Supabase query failed");
  }
}
