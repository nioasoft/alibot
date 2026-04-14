import type { Metadata } from "next";
import Link from "next/link";
import { Header } from "@/components/Header";
import { SocialLinks } from "@/components/SocialLinks";
import { Footer } from "@/components/Footer";

export const revalidate = 300;

export const metadata: Metadata = {
  title: "קבוצות הדילים שלנו",
  description:
    "כל קבוצות הדילים של מכורים לדילים ומבצעים במקום אחד: טלגרם, וואטסאפ ופייסבוק.",
  alternates: {
    canonical: "/",
  },
};

const BENEFITS = [
  "דילים חמים שממוינים לפי נושא כדי שלא תקבלו רעש מיותר.",
  "קבוצות ייעודיות לטכנולוגיה, בית, אופנה, ספורט ויופי.",
  "עדכונים מהירים עם לינקים, קופונים והפניות ישירות לקנייה.",
];

export default function HomePage() {
  return (
    <>
      <Header />

      <main>
        <section className="relative overflow-hidden bg-[radial-gradient(circle_at_top,#fff6e8_0%,#fff_42%,#eef3ff_100%)]">
          <div
            aria-hidden="true"
            className="absolute inset-x-0 top-0 h-24 bg-[linear-gradient(90deg,rgba(255,107,0,0.18),rgba(30,42,74,0.08),rgba(255,107,0,0.14))]"
          />
          <div className="mx-auto max-w-6xl px-4 py-10 md:py-16">
            <div className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
              <div>
                <p className="inline-flex rounded-full border border-brand-orange/20 bg-white/90 px-4 py-1 text-sm font-bold text-brand-orange shadow-sm">
                  כל הקבוצות במקום אחד
                </p>
                <h1 className="mt-4 max-w-3xl text-4xl font-extrabold leading-tight text-brand-navy md:text-6xl">
                  הצטרפו לקבוצות הדילים שלנו וקבלו רק את מה שמעניין אתכם
                </h1>
                <p className="mt-4 max-w-2xl text-base leading-8 text-brand-navy/75 md:text-lg">
                  טלגרם, וואטסאפ ופייסבוק מסודרים לפי נושאים. בוחרים פלטפורמה,
                  מצטרפים בלחיצה, ומתחילים לקבל דילים חמים בלי לעבור בין עשרות
                  קישורים ועמודים.
                </p>

                <div className="mt-6 flex flex-wrap gap-3">
                  <Link
                    href="#groups"
                    className="inline-flex items-center justify-center rounded-full bg-brand-orange px-6 py-3 text-sm font-extrabold text-white transition hover:bg-brand-orange-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-orange"
                  >
                    מעבר לקבוצות
                  </Link>
                  <Link
                    href="/terms"
                    className="inline-flex items-center justify-center rounded-full border border-brand-navy/15 bg-white px-6 py-3 text-sm font-bold text-brand-navy transition hover:border-brand-orange/35 hover:text-brand-orange focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-orange"
                  >
                    תקנון ותנאים
                  </Link>
                </div>
              </div>

              <aside className="rounded-[2rem] border border-white/70 bg-white/90 p-6 shadow-[0_30px_70px_rgba(30,42,74,0.12)] backdrop-blur">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.22em] text-brand-orange">
                      למה להצטרף
                    </p>
                    <h2 className="mt-2 text-2xl font-extrabold text-brand-navy">
                      פחות רעש, יותר דילים רלוונטיים
                    </h2>
                  </div>
                  <div className="rounded-2xl bg-brand-navy px-4 py-3 text-center text-white shadow-lg">
                    <div className="text-2xl font-extrabold">24/7</div>
                    <div className="text-xs text-white/70">עדכונים</div>
                  </div>
                </div>

                <ul className="mt-6 space-y-3" aria-label="יתרונות ההצטרפות">
                  {BENEFITS.map((benefit) => (
                    <li
                      key={benefit}
                      className="flex items-start gap-3 rounded-2xl border border-brand-navy/8 bg-brand-navy/[0.03] px-4 py-4"
                    >
                      <span
                        aria-hidden="true"
                        className="mt-1 inline-flex h-6 w-6 items-center justify-center rounded-full bg-brand-orange text-sm font-black text-white"
                      >
                        ✓
                      </span>
                      <span className="text-sm leading-7 text-brand-navy/80">
                        {benefit}
                      </span>
                    </li>
                  ))}
                </ul>
              </aside>
            </div>
          </div>
        </section>

        <SocialLinks />
      </main>

      <Footer />
    </>
  );
}
