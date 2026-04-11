import Link from "next/link";
import { notFound } from "next/navigation";
import { Header } from "@/components/Header";
import { SocialLinks } from "@/components/SocialLinks";
import { DealGrid } from "@/components/DealGrid";
import { Pagination } from "@/components/Pagination";
import { Footer } from "@/components/Footer";
import { getDealsByCategory } from "@/lib/deals";
import { CATEGORIES, CATEGORY_SLUGS, getCategoryMeta } from "@/lib/categories";

export const revalidate = 300;

const PER_PAGE = 24;

export function generateStaticParams() {
  return CATEGORY_SLUGS.map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const category = CATEGORIES[slug];
  if (!category) return {};

  return {
    title: `${category.icon} ${category.name} | מכורים לדילים ומבצעים`,
    description: `הדילים הכי חמים בקטגוריית ${category.name} - מכורים לדילים ומבצעים`,
  };
}

interface CategoryPageProps {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ page?: string }>;
}

export default async function CategoryPage({
  params,
  searchParams,
}: CategoryPageProps) {
  const { slug } = await params;
  const { page: pageStr } = await searchParams;

  if (!CATEGORY_SLUGS.includes(slug)) {
    notFound();
  }

  const category = getCategoryMeta(slug);
  const page = Math.max(1, parseInt(pageStr ?? "1", 10) || 1);
  const { deals, total } = await getDealsByCategory(slug, page, PER_PAGE);
  const totalPages = Math.ceil(total / PER_PAGE);

  return (
    <>
      <Header />
      <SocialLinks />

      <main className="mx-auto max-w-6xl px-4 flex-1 py-6">
        {/* Breadcrumb */}
        <nav className="mb-4 text-sm text-gray-500">
          <Link href="/" className="hover:text-brand-orange transition-colors">
            ראשי
          </Link>
          <span className="mx-2">›</span>
          <span className="text-brand-navy font-medium">
            {category.icon} {category.name}
          </span>
        </nav>

        {/* Title */}
        <h1 className="text-2xl md:text-3xl font-bold text-brand-navy mb-6">
          {category.icon} {category.name}
          <span className="text-sm font-normal text-gray-400 ms-2">
            ({total} דילים)
          </span>
        </h1>

        {/* Grid */}
        <DealGrid deals={deals} />

        {/* Pagination */}
        <Pagination
          currentPage={page}
          totalPages={totalPages}
          basePath={`/category/${slug}`}
        />
      </main>

      <Footer />
    </>
  );
}
