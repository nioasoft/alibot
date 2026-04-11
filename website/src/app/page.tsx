import { Header } from "@/components/Header";
import { SocialLinks } from "@/components/SocialLinks";
import { CategorySection } from "@/components/CategorySection";
import { Footer } from "@/components/Footer";
import { getAllLatestDeals } from "@/lib/deals";
import { CATEGORIES, CATEGORY_SLUGS } from "@/lib/categories";

export const revalidate = 300;

export default async function HomePage() {
  const dealsByCategory = await getAllLatestDeals(6);

  return (
    <>
      <Header />
      <SocialLinks />

      <main className="mx-auto max-w-6xl px-4 pb-8">
        {CATEGORY_SLUGS.map((slug) => {
          const deals = dealsByCategory[slug] ?? [];
          return (
            <CategorySection
              key={slug}
              category={CATEGORIES[slug]}
              deals={deals}
            />
          );
        })}

        {Object.keys(dealsByCategory).length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <p className="text-lg">עוד אין דילים - חזרו בקרוב!</p>
          </div>
        )}
      </main>

      <Footer />
    </>
  );
}
