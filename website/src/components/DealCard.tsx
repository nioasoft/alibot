import Image from "next/image";
import type { Deal } from "@/lib/types";
import { getCategoryMeta } from "@/lib/categories";

interface DealCardProps {
  deal: Deal;
  showCategory?: boolean;
}

function formatPrice(deal: Deal): string {
  if (!deal.price || deal.price <= 0) {
    return "ראה מחיר";
  }
  if (deal.currency === "ILS" || deal.price_ils) {
    const ils = deal.price_ils ?? deal.price;
    return `₪${ils.toFixed(0)}`;
  }
  if (deal.currency === "USD") {
    const ilsStr = deal.price_ils ? ` (כ-₪${deal.price_ils.toFixed(0)})` : "";
    return `$${deal.price.toFixed(2)}${ilsStr}`;
  }
  return `${deal.price}`;
}

function formatOriginalPrice(deal: Deal): string | null {
  if (!deal.original_price || deal.original_price <= deal.price) return null;
  if (deal.currency === "USD") return `$${deal.original_price.toFixed(2)}`;
  return `₪${deal.original_price.toFixed(0)}`;
}

export function DealCard({ deal, showCategory = false }: DealCardProps) {
  const category = getCategoryMeta(deal.category);
  const originalPrice = formatOriginalPrice(deal);
  const link = deal.affiliate_link || deal.product_link;

  return (
    <article className="group bg-card-bg rounded-xl shadow-sm hover:shadow-md transition-shadow overflow-hidden flex flex-col">
      {/* Image */}
      <div className="relative aspect-square bg-gray-100">
        {deal.image_url ? (
          <Image
            src={deal.image_url}
            alt={deal.product_name}
            fill
            sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 16vw"
            className="object-cover group-hover:scale-105 transition-transform duration-300"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-gray-300">
            <svg
              className="w-12 h-12"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5a1.5 1.5 0 001.5-1.5V4.5a1.5 1.5 0 00-1.5-1.5H3.75a1.5 1.5 0 00-1.5 1.5v15a1.5 1.5 0 001.5 1.5z"
              />
            </svg>
          </div>
        )}

        {/* Category badge */}
        {showCategory && (
          <span
            className="absolute top-2 start-2 rounded-full px-2 py-0.5 text-xs font-bold text-white"
            style={{ backgroundColor: category.color }}
          >
            {category.icon} {category.name}
          </span>
        )}
      </div>

      {/* Content */}
      <div className="flex flex-col flex-1 p-3">
        <h3 className="text-sm font-semibold text-brand-navy line-clamp-2 mb-2 leading-snug">
          {deal.product_name}
        </h3>

        <div className="mt-auto">
          {/* Price */}
          <div className="flex items-baseline gap-2 mb-2">
            <span className="text-lg font-bold text-brand-orange">
              {formatPrice(deal)}
            </span>
            {originalPrice && (
              <span className="text-xs text-gray-400 line-through">
                {originalPrice}
              </span>
            )}
          </div>

          {/* CTA */}
          <a
            href={link}
            target="_blank"
            rel="noopener noreferrer"
            className="
              block w-full text-center rounded-lg py-2.5
              bg-brand-orange hover:bg-brand-orange-hover
              text-white text-sm font-bold
              transition-colors min-h-[44px]
              flex items-center justify-center
            "
          >
            🛒 לדיל
          </a>
        </div>
      </div>
    </article>
  );
}
