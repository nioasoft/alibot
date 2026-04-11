import Link from "next/link";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  basePath: string;
}

export function Pagination({
  currentPage,
  totalPages,
  basePath,
}: PaginationProps) {
  if (totalPages <= 1) return null;

  const pages: number[] = [];
  const start = Math.max(1, currentPage - 2);
  const end = Math.min(totalPages, currentPage + 2);
  for (let i = start; i <= end; i++) {
    pages.push(i);
  }

  function pageUrl(page: number): string {
    if (page === 1) return basePath;
    return `${basePath}?page=${page}`;
  }

  return (
    <nav className="flex items-center justify-center gap-2 py-6" dir="ltr">
      {/* Previous */}
      {currentPage > 1 ? (
        <Link
          href={pageUrl(currentPage - 1)}
          className="px-3 py-2 rounded-lg bg-white text-brand-navy hover:bg-gray-100 transition-colors min-h-[44px] flex items-center"
        >
          ‹
        </Link>
      ) : (
        <span className="px-3 py-2 rounded-lg bg-gray-100 text-gray-300 min-h-[44px] flex items-center">
          ‹
        </span>
      )}

      {/* Page numbers */}
      {pages.map((page) => (
        <Link
          key={page}
          href={pageUrl(page)}
          className={`
            px-3 py-2 rounded-lg min-h-[44px] flex items-center transition-colors
            ${
              page === currentPage
                ? "bg-brand-orange text-white font-bold"
                : "bg-white text-brand-navy hover:bg-gray-100"
            }
          `}
        >
          {page}
        </Link>
      ))}

      {/* Next */}
      {currentPage < totalPages ? (
        <Link
          href={pageUrl(currentPage + 1)}
          className="px-3 py-2 rounded-lg bg-white text-brand-navy hover:bg-gray-100 transition-colors min-h-[44px] flex items-center"
        >
          ›
        </Link>
      ) : (
        <span className="px-3 py-2 rounded-lg bg-gray-100 text-gray-300 min-h-[44px] flex items-center">
          ›
        </span>
      )}
    </nav>
  );
}
