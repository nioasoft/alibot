import type { CategoryMeta } from "./types";

export const CATEGORIES: Record<string, CategoryMeta> = {
  tech: { slug: "tech", name: "טכנולוגיה", icon: "💻", color: "#3B82F6" },
  home: { slug: "home", name: "בית", icon: "🏠", color: "#10B981" },
  fashion: { slug: "fashion", name: "אופנה", icon: "👗", color: "#EC4899" },
  beauty: { slug: "beauty", name: "יופי", icon: "💄", color: "#8B5CF6" },
  toys: { slug: "toys", name: "צעצועים", icon: "🧸", color: "#F59E0B" },
  sports: { slug: "sports", name: "ספורט", icon: "⚽", color: "#EF4444" },
  auto: { slug: "auto", name: "רכב", icon: "🚗", color: "#6B7280" },
  other: { slug: "other", name: "כללי", icon: "🛍️", color: "#F97316" },
};

export const CATEGORY_SLUGS = Object.keys(CATEGORIES);

export function getCategoryMeta(slug: string): CategoryMeta {
  return CATEGORIES[slug] ?? CATEGORIES.other;
}
