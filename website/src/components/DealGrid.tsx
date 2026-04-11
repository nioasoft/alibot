import type { Deal } from "@/lib/types";
import { DealCard } from "./DealCard";

interface DealGridProps {
  deals: Deal[];
  showCategory?: boolean;
}

export function DealGrid({ deals, showCategory = false }: DealGridProps) {
  if (deals.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        <p>אין דילים כרגע</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3 md:gap-4">
      {deals.map((deal) => (
        <DealCard key={deal.id} deal={deal} showCategory={showCategory} />
      ))}
    </div>
  );
}
