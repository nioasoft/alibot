import { NextRequest, NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import { getClickContext, isPreviewCrawler } from "@/lib/tracking";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const SITE_NAME = "מכורים לדילים ומבצעים";
const DEFAULT_OG_IMAGE = "/og-image.jpg";
const AUTO_REDIRECT_DELAY_MS = 700;

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ token: string }> }
) {
  try {
    const { token } = await context.params;
    const normalizedToken = token.trim();

    if (!normalizedToken) {
      return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    const supabase = getSupabaseAdmin();
    const { data: link, error: lookupError } = await supabase
      .from("tracking_links")
      .select("id, target_url, metadata")
      .eq("token", normalizedToken)
      .maybeSingle();

    if (lookupError) {
      throw lookupError;
    }

    if (!link?.target_url || !link.id) {
      return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    const metadata = coerceMetadata(link.metadata);
    const pageUrl = request.nextUrl.toString();
    const title = buildTitle(metadata.product_name);
    const description = buildDescription(metadata.category);
    const imageUrl = buildImageUrl(request.nextUrl.origin, DEFAULT_OG_IMAGE);
    const isCrawler = isPreviewCrawler(request.headers.get("user-agent"));

    if (isCrawler) {
      return htmlResponse(
        renderPreviewHtml({
          pageUrl,
          title,
          description,
          imageUrl,
        })
      );
    }

    await recordHumanClick({
      supabase,
      request,
      linkId: link.id,
      token: normalizedToken,
    });

    return htmlResponse(
      renderHumanLandingHtml({
        pageUrl,
        title,
        description,
        imageUrl,
        targetUrl: String(link.target_url),
      })
    );
  } catch {
    return NextResponse.json(
      { error: "Tracking redirect failed" },
      { status: 500 }
    );
  }
}

async function recordHumanClick({
  supabase,
  request,
  linkId,
  token,
}: {
  supabase: ReturnType<typeof getSupabaseAdmin>;
  request: NextRequest;
  linkId: string;
  token: string;
}) {
  const clickContext = getClickContext(request);
  const clickedAt = new Date().toISOString();

  try {
    const { error: clickError } = await supabase
      .from("tracking_click_events")
      .insert({
        tracking_link_id: linkId,
        token,
        clicked_at: clickedAt,
        ip_hash: clickContext.ipHash,
        user_agent: clickContext.userAgent,
        referer: clickContext.referer,
        country_code: clickContext.countryCode,
        cf_ray: clickContext.cfRay,
      });

    if (clickError) {
      throw clickError;
    }

    const { error: rpcError } = await supabase.rpc(
      "increment_tracking_link_clicks",
      {
        link_id: linkId,
        clicked_at: clickedAt,
      }
    );

    if (rpcError) {
      throw rpcError;
    }
  } catch (error) {
    console.error("Failed to record tracking click", error);
  }
}

function buildTitle(productName: string | null): string {
  if (!productName) {
    return `${SITE_NAME} | מעביר אותך לדיל`;
  }

  return `${productName} | ${SITE_NAME}`;
}

function buildDescription(category: string | null): string {
  if (!category) {
    return "פותחים את הדיל דרך הקישור הרשמי של AliExpress.";
  }

  return `דיל בקטגוריית ${category}. פותחים דרך הקישור הרשמי של AliExpress.`;
}

function buildImageUrl(origin: string, path: string): string {
  return `${origin}${path}`;
}

function renderPreviewHtml({
  pageUrl,
  title,
  description,
  imageUrl,
}: {
  pageUrl: string;
  title: string;
  description: string;
  imageUrl: string;
}) {
  return `<!doctype html>
<html lang="he" dir="rtl">
  <head>
    <meta charset="utf-8" />
    <title>${escapeHtml(title)}</title>
    <meta name="description" content="${escapeHtml(description)}" />
    <meta name="robots" content="noindex, nofollow, noarchive" />
    <meta property="og:type" content="website" />
    <meta property="og:title" content="${escapeHtml(title)}" />
    <meta property="og:description" content="${escapeHtml(description)}" />
    <meta property="og:url" content="${escapeHtml(pageUrl)}" />
    <meta property="og:image" content="${escapeHtml(imageUrl)}" />
    <meta property="og:site_name" content="${escapeHtml(SITE_NAME)}" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="${escapeHtml(title)}" />
    <meta name="twitter:description" content="${escapeHtml(description)}" />
    <meta name="twitter:image" content="${escapeHtml(imageUrl)}" />
    <style>
      body {
        font-family: sans-serif;
        background: #fff7ee;
        color: #1f2937;
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
      }
      main {
        max-width: 40rem;
        padding: 2rem;
        text-align: center;
      }
      h1 {
        font-size: 1.4rem;
        margin: 0 0 0.75rem;
      }
      p {
        margin: 0;
        line-height: 1.6;
      }
    </style>
  </head>
  <body>
    <main>
      <h1>${escapeHtml(title)}</h1>
      <p>${escapeHtml(description)}</p>
    </main>
  </body>
</html>`;
}

function renderHumanLandingHtml({
  pageUrl,
  title,
  description,
  imageUrl,
  targetUrl,
}: {
  pageUrl: string;
  title: string;
  description: string;
  imageUrl: string;
  targetUrl: string;
}) {
  return `<!doctype html>
<html lang="he" dir="rtl">
  <head>
    <meta charset="utf-8" />
    <title>${escapeHtml(title)}</title>
    <meta name="description" content="${escapeHtml(description)}" />
    <meta name="robots" content="noindex, nofollow, noarchive" />
    <meta property="og:type" content="website" />
    <meta property="og:title" content="${escapeHtml(title)}" />
    <meta property="og:description" content="${escapeHtml(description)}" />
    <meta property="og:url" content="${escapeHtml(pageUrl)}" />
    <meta property="og:image" content="${escapeHtml(imageUrl)}" />
    <meta property="og:site_name" content="${escapeHtml(SITE_NAME)}" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="${escapeHtml(title)}" />
    <meta name="twitter:description" content="${escapeHtml(description)}" />
    <meta name="twitter:image" content="${escapeHtml(imageUrl)}" />
    <meta http-equiv="refresh" content="8;url=${escapeHtml(targetUrl)}" />
    <style>
      body {
        font-family: sans-serif;
        background: linear-gradient(180deg, #fff7ee 0%, #ffffff 100%);
        color: #111827;
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
      }
      main {
        max-width: 34rem;
        padding: 2rem;
        text-align: center;
      }
      h1 {
        margin: 0 0 0.75rem;
        font-size: 1.5rem;
      }
      p {
        margin: 0 0 1.25rem;
        line-height: 1.7;
      }
      a {
        display: inline-block;
        background: #ff6b00;
        color: #fff;
        text-decoration: none;
        padding: 0.9rem 1.3rem;
        border-radius: 999px;
        font-weight: 700;
      }
      small {
        display: block;
        margin-top: 1rem;
        color: #6b7280;
      }
    </style>
  </head>
  <body>
    <main>
      <h1>${escapeHtml(title)}</h1>
      <p>${escapeHtml(description)}</p>
      <a href="${escapeHtml(targetUrl)}" rel="noreferrer">להמשך לדיל ב-AliExpress</a>
      <small>אם לא הועברת אוטומטית, אפשר ללחוץ על הכפתור.</small>
    </main>
    <script>
      window.setTimeout(function () {
        window.location.replace(${JSON.stringify(targetUrl)});
      }, ${AUTO_REDIRECT_DELAY_MS});
    </script>
  </body>
</html>`;
}

function htmlResponse(html: string) {
  return new NextResponse(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

function coerceMetadata(value: unknown): {
  product_name: string | null;
  category: string | null;
} {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {
      product_name: null,
      category: null,
    };
  }

  const metadata = value as Record<string, unknown>;
  return {
    product_name: asNullableString(metadata.product_name),
    category: asNullableString(metadata.category),
  };
}

function asNullableString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }

  const trimmed = value.trim();
  return trimmed || null;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
