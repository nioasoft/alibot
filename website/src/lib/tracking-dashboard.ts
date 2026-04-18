import { getSupabaseAdmin } from "@/lib/supabase-admin";

export interface TrackingSummary {
  totalLinks: number;
  totalClicks: number;
  clickedLinks: number;
  lastClickAt: string | null;
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
  ]);

  throwIfError(totalLinksResult.error);
  throwIfError(totalClicksResult.error);
  throwIfError(clickedLinksResult.error);
  throwIfError(lastClickResult.error);
  throwIfError(topLinksResult.error);
  throwIfError(recentLinksResult.error);
  throwIfError(categoryLinksResult.error);
  throwIfError(recentClicksResult.error);

  const categoryStats = buildCategoryStats(categoryLinksResult.data ?? []);

  return {
    summary: {
      totalLinks: totalLinksResult.count ?? 0,
      totalClicks: totalClicksResult.count ?? 0,
      clickedLinks: clickedLinksResult.count ?? 0,
      lastClickAt: lastClickResult.data?.last_clicked_at ?? null,
    } satisfies TrackingSummary,
    categoryStats,
    topLinks: (topLinksResult.data ?? []).map(mapLinkRow),
    recentLinks: (recentLinksResult.data ?? []).map(mapLinkRow),
    recentClicks: (recentClicksResult.data ?? []).map(mapClickRow),
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
