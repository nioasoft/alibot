import { NextRequest, NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import { getClickContext } from "@/lib/tracking";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

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
      .select("id, target_url")
      .eq("token", normalizedToken)
      .maybeSingle();

    if (lookupError) {
      throw lookupError;
    }

    if (!link?.target_url || !link.id) {
      return NextResponse.json({ error: "Not found" }, { status: 404 });
    }

    const clickContext = getClickContext(request);
    const clickedAt = new Date().toISOString();
    try {
      const { error: clickError } = await supabase
        .from("tracking_click_events")
        .insert({
          tracking_link_id: link.id,
          token: normalizedToken,
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
          link_id: link.id,
          clicked_at: clickedAt,
        }
      );

      if (rpcError) {
        throw rpcError;
      }
    } catch (error) {
      console.error("Failed to record tracking click", error);
    }

    const response = NextResponse.redirect(link.target_url, 302);
    response.headers.set("Cache-Control", "no-store");
    return response;
  } catch {
    return NextResponse.json({ error: "Tracking redirect failed" }, { status: 500 });
  }
}
