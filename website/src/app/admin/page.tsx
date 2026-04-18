import type { Metadata } from "next";
import Link from "next/link";
import { getTrackingDashboardData } from "@/lib/tracking-dashboard";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Tracking Admin",
  robots: {
    index: false,
    follow: false,
  },
};

export default async function TrackingAdminPage() {
  const { summary, topLinks, recentLinks, recentClicks } =
    await getTrackingDashboardData();

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#fff6e8_0%,#fff_42%,#eef3ff_100%)] px-4 py-8">
      <div className="mx-auto max-w-7xl space-y-8">
        <section className="rounded-[2rem] border border-white/70 bg-white/90 p-6 shadow-[0_30px_70px_rgba(30,42,74,0.12)] backdrop-blur">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.24em] text-brand-orange">
                Tracking Admin
              </p>
              <h1 className="mt-2 text-3xl font-extrabold text-brand-navy md:text-4xl">
                לוח בקרה ללינקים והקלקות
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-brand-navy/70 md:text-base">
                מעקב אחרי הלינקים שיוצאים מהבוט, הקליקים שהם מקבלים, והפעילות
                האחרונה שנרשמה בשרת.
              </p>
            </div>

            <div className="rounded-3xl border border-brand-orange/15 bg-brand-orange/6 px-5 py-4 text-sm text-brand-navy">
              <div className="font-bold">קליק אחרון</div>
              <div className="mt-1 text-brand-navy/75">
                {formatDateTime(summary.lastClickAt)}
              </div>
            </div>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-3">
            <SummaryCard
              label="סה״כ לינקים"
              value={summary.totalLinks.toLocaleString("en-US")}
            />
            <SummaryCard
              label="סה״כ קליקים"
              value={summary.totalClicks.toLocaleString("en-US")}
            />
            <SummaryCard
              label="לינקים עם קליקים"
              value={summary.clickedLinks.toLocaleString("en-US")}
            />
          </div>
        </section>

        <section className="grid gap-8 xl:grid-cols-[1.15fr_0.85fr]">
          <Panel title="Top Links" subtitle="הקישורים עם הכי הרבה קליקים">
            <div className="overflow-x-auto">
              <table className="min-w-full text-right text-sm">
                <thead className="text-brand-navy/55">
                  <tr className="border-b border-brand-navy/10">
                    <th className="px-3 py-3 font-bold">יעד</th>
                    <th className="px-3 py-3 font-bold">מקור</th>
                    <th className="px-3 py-3 font-bold">קליקים</th>
                    <th className="px-3 py-3 font-bold">לינק</th>
                  </tr>
                </thead>
                <tbody>
                  {topLinks.length ? (
                    topLinks.map((link) => (
                      <tr key={`top-${link.token}`} className="border-b border-brand-navy/8">
                        <td className="px-3 py-3 align-top">
                          <div className="font-bold text-brand-navy">
                            {link.platform || "unknown"} /{" "}
                            {link.destinationKey || "unknown"}
                          </div>
                          <div className="mt-1 text-xs text-brand-navy/60">
                            {formatDateTime(link.lastClickedAt)}
                          </div>
                        </td>
                        <td className="px-3 py-3 align-top text-brand-navy/70">
                          {link.sourceGroup || "unknown"}
                        </td>
                        <td className="px-3 py-3 align-top font-extrabold text-brand-orange">
                          {link.clickCount}
                        </td>
                        <td className="px-3 py-3 align-top">
                          <div className="max-w-[16rem] truncate font-mono text-xs text-brand-navy/70">
                            {link.token}
                          </div>
                          <Link
                            href={buildTrackedUrl(link.token)}
                            target="_blank"
                            className="mt-1 inline-block text-xs font-bold text-brand-orange hover:text-brand-orange-hover"
                          >
                            פתח לינק
                          </Link>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <EmptyRow colSpan={4} label="עדיין אין קישורים עם קליקים." />
                  )}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel title="Recent Clicks" subtitle="ההקלקות האחרונות שנרשמו">
            <div className="space-y-3">
              {recentClicks.length ? (
                recentClicks.map((click) => (
                  <article
                    key={`${click.token}-${click.clickedAt}`}
                    className="rounded-3xl border border-brand-navy/10 bg-brand-navy/[0.03] px-4 py-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-bold text-brand-navy">
                          {click.platform || "unknown"} /{" "}
                          {click.destinationKey || "unknown"}
                        </div>
                        <div className="mt-1 font-mono text-xs text-brand-navy/60">
                          {click.token}
                        </div>
                      </div>
                      <div className="text-xs text-brand-navy/60">
                        {formatDateTime(click.clickedAt)}
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs text-brand-navy/70">
                      <Badge>{click.countryCode || "??"}</Badge>
                      <Badge>{click.sourceGroup || "unknown source"}</Badge>
                      <Badge>{shortenReferer(click.referer)}</Badge>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState label="עדיין לא נרשמו קליקים." />
              )}
            </div>
          </Panel>
        </section>

        <Panel title="Recent Links" subtitle="הלינקים האחרונים שנוצרו">
          <div className="overflow-x-auto">
            <table className="min-w-full text-right text-sm">
              <thead className="text-brand-navy/55">
                <tr className="border-b border-brand-navy/10">
                  <th className="px-3 py-3 font-bold">נוצר</th>
                  <th className="px-3 py-3 font-bold">יעד</th>
                  <th className="px-3 py-3 font-bold">מקור</th>
                  <th className="px-3 py-3 font-bold">קליקים</th>
                  <th className="px-3 py-3 font-bold">לינק מנוטר</th>
                  <th className="px-3 py-3 font-bold">יעד סופי</th>
                </tr>
              </thead>
              <tbody>
                {recentLinks.length ? (
                  recentLinks.map((link) => (
                    <tr key={link.token} className="border-b border-brand-navy/8">
                      <td className="px-3 py-3 align-top text-brand-navy/70">
                        {formatDateTime(link.createdAt)}
                      </td>
                      <td className="px-3 py-3 align-top">
                        <div className="font-bold text-brand-navy">
                          {link.platform || "unknown"} /{" "}
                          {link.destinationKey || "unknown"}
                        </div>
                        <div className="mt-1 text-xs text-brand-navy/60">
                          קליק אחרון: {formatDateTime(link.lastClickedAt)}
                        </div>
                      </td>
                      <td className="px-3 py-3 align-top text-brand-navy/70">
                        {link.sourceGroup || "unknown"}
                      </td>
                      <td className="px-3 py-3 align-top font-extrabold text-brand-orange">
                        {link.clickCount}
                      </td>
                      <td className="px-3 py-3 align-top">
                        <Link
                          href={buildTrackedUrl(link.token)}
                          target="_blank"
                          className="font-mono text-xs text-brand-orange hover:text-brand-orange-hover"
                        >
                          {buildTrackedUrl(link.token)}
                        </Link>
                      </td>
                      <td className="px-3 py-3 align-top">
                        <Link
                          href={link.targetUrl}
                          target="_blank"
                          className="inline-block max-w-[20rem] truncate text-xs text-brand-navy/70 hover:text-brand-orange"
                        >
                          {link.targetUrl}
                        </Link>
                      </td>
                    </tr>
                  ))
                ) : (
                  <EmptyRow colSpan={6} label="עדיין לא נוצרו לינקים." />
                )}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </main>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-3xl border border-brand-navy/10 bg-brand-navy px-5 py-5 text-white shadow-lg">
      <div className="text-sm text-white/70">{label}</div>
      <div className="mt-3 text-3xl font-extrabold">{value}</div>
    </div>
  );
}

function Panel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-[2rem] border border-white/70 bg-white/90 p-6 shadow-[0_20px_50px_rgba(30,42,74,0.1)] backdrop-blur">
      <div className="mb-5">
        <h2 className="text-2xl font-extrabold text-brand-navy">{title}</h2>
        <p className="mt-1 text-sm text-brand-navy/65">{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full bg-white px-3 py-1 font-bold text-brand-navy shadow-sm">
      {children}
    </span>
  );
}

function EmptyRow({ colSpan, label }: { colSpan: number; label: string }) {
  return (
    <tr>
      <td
        colSpan={colSpan}
        className="px-3 py-8 text-center text-sm text-brand-navy/60"
      >
        {label}
      </td>
    </tr>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="rounded-3xl border border-dashed border-brand-navy/15 bg-brand-navy/[0.02] px-4 py-8 text-center text-sm text-brand-navy/60">
      {label}
    </div>
  );
}

function buildTrackedUrl(token: string) {
  const baseUrl =
    process.env.TRACKING_BASE_URL?.replace(/\/+$/, "") ?? "https://trk.dilim.net";
  return `${baseUrl}/go/${token}`;
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "עדיין אין";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("he-IL", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function shortenReferer(referer: string | null) {
  if (!referer) {
    return "direct";
  }

  try {
    return new URL(referer).hostname;
  } catch {
    return referer.slice(0, 40);
  }
}
