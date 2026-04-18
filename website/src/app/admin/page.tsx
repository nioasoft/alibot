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
  const {
    summary,
    orderSummary,
    categoryStats,
    orderCategoryStats,
    topLinks,
    recentLinks,
    recentClicks,
    recentOrders,
  } =
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

        <section className="rounded-[2rem] border border-white/70 bg-white/90 p-6 shadow-[0_30px_70px_rgba(30,42,74,0.12)] backdrop-blur">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.24em] text-brand-orange">
                Affiliate Orders
              </p>
              <h2 className="mt-2 text-2xl font-extrabold text-brand-navy md:text-3xl">
                הזמנות ועמלות מ־AliExpress
              </h2>
            </div>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-4">
            <SummaryCard
              label="סה״כ הזמנות"
              value={orderSummary.totalOrders.toLocaleString("en-US")}
            />
            <SummaryCard
              label="עם שיוך קטגוריה"
              value={orderSummary.attributedOrders.toLocaleString("en-US")}
            />
            <SummaryCard
              label="Legacy / לא משויך"
              value={orderSummary.unattributedOrders.toLocaleString("en-US")}
            />
            <SummaryCard
              label="עמלה משויכת"
              value={`$${orderSummary.attributedFinishedCommission.toFixed(2)}`}
            />
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <SummaryCard
              label="Payment Completed"
              value={orderSummary.paymentCompletedOrders.toLocaleString("en-US")}
            />
            <SummaryCard
              label="Buyer Confirmed"
              value={orderSummary.buyerConfirmedOrders.toLocaleString("en-US")}
            />
            <SummaryCard
              label="עמלה משוערת"
              value={`$${orderSummary.estimatedFinishedCommission.toFixed(2)}`}
            />
          </div>

          <p className="mt-4 text-sm leading-7 text-brand-navy/65">
            קטגוריות ההזמנות מחושבות רק עבור הזמנות עם שיוך ברור. הזמנות היסטוריות
            ישנות של החשבון, שלא ניתנות לשיוך אמין למערכת שלנו, מסומנות כ־legacy
            או לא משויכות.
          </p>
        </section>

        <section className="grid gap-8 xl:grid-cols-[1.15fr_0.85fr]">
          <Panel title="Categories" subtitle="אילו קטגוריות מושכות יותר קליקים">
            <div className="overflow-x-auto">
              <table className="min-w-full text-right text-sm">
                <thead className="text-brand-navy/55">
                  <tr className="border-b border-brand-navy/10">
                    <th className="px-3 py-3 font-bold">קטגוריה</th>
                    <th className="px-3 py-3 font-bold">לינקים</th>
                    <th className="px-3 py-3 font-bold">קליקים</th>
                  </tr>
                </thead>
                <tbody>
                  {categoryStats.length ? (
                    categoryStats.slice(0, 10).map((row) => (
                      <tr key={row.category} className="border-b border-brand-navy/8">
                        <td className="px-3 py-3 align-top">
                          <span className="rounded-full bg-brand-orange/10 px-3 py-1 font-bold text-brand-orange">
                            {row.category}
                          </span>
                        </td>
                        <td className="px-3 py-3 align-top text-brand-navy/70">
                          {row.links}
                        </td>
                        <td className="px-3 py-3 align-top font-extrabold text-brand-orange">
                          {row.clicks}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <EmptyRow colSpan={3} label="עדיין אין קטגוריות שנמדדו." />
                  )}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel title="Top Links" subtitle="הקישורים עם הכי הרבה קליקים">
            <div className="overflow-x-auto">
              <table className="min-w-full text-right text-sm">
                <thead className="text-brand-navy/55">
                  <tr className="border-b border-brand-navy/10">
                    <th className="px-3 py-3 font-bold">יעד</th>
                    <th className="px-3 py-3 font-bold">קטגוריה</th>
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
                          {renderCategory(link.category)}
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
                    <EmptyRow colSpan={5} label="עדיין אין קישורים עם קליקים." />
                  )}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel
            title="Order Categories"
            subtitle="קטגוריות עם יותר הזמנות ועמלה משוערת"
          >
            <div className="overflow-x-auto">
              <table className="min-w-full text-right text-sm">
                <thead className="text-brand-navy/55">
                  <tr className="border-b border-brand-navy/10">
                    <th className="px-3 py-3 font-bold">קטגוריה</th>
                    <th className="px-3 py-3 font-bold">הזמנות</th>
                    <th className="px-3 py-3 font-bold">עמלה משוערת</th>
                  </tr>
                </thead>
                <tbody>
                  {orderCategoryStats.length ? (
                    orderCategoryStats.slice(0, 10).map((row) => (
                      <tr key={`orders-${row.category}`} className="border-b border-brand-navy/8">
                        <td className="px-3 py-3 align-top">
                          <span className="rounded-full bg-brand-orange/10 px-3 py-1 font-bold text-brand-orange">
                            {row.category}
                          </span>
                        </td>
                        <td className="px-3 py-3 align-top text-brand-navy/70">
                          {row.orders}
                        </td>
                        <td className="px-3 py-3 align-top font-extrabold text-brand-orange">
                          ${row.estimatedFinishedCommission.toFixed(2)}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <EmptyRow colSpan={3} label="עדיין לא סונכרנו הזמנות." />
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
                      <Badge>{click.category || "other"}</Badge>
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

        <Panel title="Recent Orders" subtitle="ההזמנות האחרונות שסונכרנו מ־AliExpress">
          <div className="overflow-x-auto">
            <table className="min-w-full text-right text-sm">
              <thead className="text-brand-navy/55">
                <tr className="border-b border-brand-navy/10">
                  <th className="px-3 py-3 font-bold">נוצר</th>
                  <th className="px-3 py-3 font-bold">סטטוס</th>
                  <th className="px-3 py-3 font-bold">קטגוריה</th>
                  <th className="px-3 py-3 font-bold">מוצר</th>
                  <th className="px-3 py-3 font-bold">חשבון</th>
                  <th className="px-3 py-3 font-bold">Tracking ID</th>
                  <th className="px-3 py-3 font-bold">עמלה</th>
                </tr>
              </thead>
              <tbody>
                {recentOrders.length ? (
                  recentOrders.map((order) => (
                    <tr key={`${order.accountKey}-${order.orderId}`} className="border-b border-brand-navy/8">
                      <td className="px-3 py-3 align-top text-brand-navy/70">
                        {formatDateTime(order.createdTime)}
                      </td>
                      <td className="px-3 py-3 align-top">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-bold text-brand-navy">
                            {order.orderStatus || "unknown"}
                          </span>
                          <span
                            className={
                              order.isAttributed
                                ? "rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] font-bold text-emerald-700"
                                : "rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-bold text-slate-600"
                            }
                          >
                            {order.isAttributed ? "attributed" : "legacy"}
                          </span>
                        </div>
                        <div className="mt-1 text-xs text-brand-navy/60">
                          סיום: {formatDateTime(order.finishedTime)}
                        </div>
                      </td>
                      <td className="px-3 py-3 align-top text-brand-navy/70">
                        {order.resolvedCategory || "לא משויך"}
                      </td>
                      <td className="px-3 py-3 align-top">
                        <div className="max-w-[18rem] truncate font-bold text-brand-navy">
                          {order.productTitle || order.productId || "unknown"}
                        </div>
                        <div className="mt-1 text-xs text-brand-navy/60">
                          {order.productId || "no product id"}
                        </div>
                      </td>
                      <td className="px-3 py-3 align-top text-brand-navy/70">
                        {order.accountKey}
                      </td>
                      <td className="px-3 py-3 align-top font-mono text-xs text-brand-navy/70">
                        {order.trackingId || "unknown"}
                      </td>
                      <td className="px-3 py-3 align-top font-extrabold text-brand-orange">
                        ${order.estimatedFinishedCommission.toFixed(2)}
                      </td>
                    </tr>
                  ))
                ) : (
                  <EmptyRow colSpan={7} label="עדיין לא סונכרנו הזמנות." />
                )}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel title="Recent Links" subtitle="הלינקים האחרונים שנוצרו">
          <div className="overflow-x-auto">
            <table className="min-w-full text-right text-sm">
              <thead className="text-brand-navy/55">
                <tr className="border-b border-brand-navy/10">
                  <th className="px-3 py-3 font-bold">נוצר</th>
                  <th className="px-3 py-3 font-bold">יעד</th>
                  <th className="px-3 py-3 font-bold">מקור</th>
                  <th className="px-3 py-3 font-bold">קטגוריה</th>
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
                      <td className="px-3 py-3 align-top text-brand-navy/70">
                        {renderCategory(link.category)}
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
                  <EmptyRow colSpan={7} label="עדיין לא נוצרו לינקים." />
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

function renderCategory(category: string | null) {
  return category || "other";
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
