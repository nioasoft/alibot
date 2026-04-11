import { supabase } from "./supabase";
import type { Deal } from "./types";

export async function getLatestDealsByCategory(
  category: string,
  limit: number = 6
): Promise<Deal[]> {
  const { data, error } = await supabase
    .from("deals")
    .select("*")
    .eq("category", category)
    .eq("is_active", true)
    .order("published_at", { ascending: false })
    .limit(limit);

  if (error) {
    console.error(`Failed to fetch deals for ${category}:`, error);
    return [];
  }

  return data ?? [];
}

export async function getDealsByCategory(
  category: string,
  page: number = 1,
  perPage: number = 24
): Promise<{ deals: Deal[]; total: number }> {
  const from = (page - 1) * perPage;
  const to = from + perPage - 1;

  const { data, error, count } = await supabase
    .from("deals")
    .select("*", { count: "exact" })
    .eq("category", category)
    .eq("is_active", true)
    .order("published_at", { ascending: false })
    .range(from, to);

  if (error) {
    console.error(`Failed to fetch deals for ${category}:`, error);
    return { deals: [], total: 0 };
  }

  return { deals: data ?? [], total: count ?? 0 };
}

export async function getAllLatestDeals(
  limit: number = 6
): Promise<Record<string, Deal[]>> {
  const { data, error } = await supabase
    .from("deals")
    .select("*")
    .eq("is_active", true)
    .order("published_at", { ascending: false })
    .limit(200);

  if (error) {
    console.error("Failed to fetch all deals:", error);
    return {};
  }

  const grouped: Record<string, Deal[]> = {};
  for (const deal of data ?? []) {
    const cat = deal.category || "other";
    if (!grouped[cat]) grouped[cat] = [];
    if (grouped[cat].length < limit) {
      grouped[cat].push(deal);
    }
  }

  return grouped;
}
