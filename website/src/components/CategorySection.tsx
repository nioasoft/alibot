import Link from "next/link";
import type { Deal } from "@/lib/types";
import type { CategoryMeta } from "@/lib/types";
import { DealGrid } from "./DealGrid";

interface CategorySectionProps {
  category: CategoryMeta;
  deals: Deal[];
}

export function CategorySection({ category, deals }: CategorySectionProps) {
  if (deals.length === 0) return null;

  return (
    <section className="py-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl md:text-2xl font-bold text-brand-navy">
          {category.icon} {category.name}
        </h2>
        <Link
          href={`/category/${category.slug}`}
          className="text-sm font-medium text-brand-orange hover:text-brand-orange-hover transition-colors"
        >
          הכל ←
        </Link>
      </div>
      <DealGrid deals={deals} />
    </section>
  );
}
