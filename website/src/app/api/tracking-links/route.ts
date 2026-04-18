import { NextRequest, NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import {
  buildTrackedUrl,
  createTrackingToken,
  getTrackingBaseUrl,
  hasValidTrackingSecret,
  validateTrackingPayload,
} from "@/lib/tracking";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  try {
    if (!hasValidTrackingSecret(request)) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const payload = validateTrackingPayload(await request.json());
    const supabase = getSupabaseAdmin();
    const baseUrl = getTrackingBaseUrl(request.nextUrl.origin);

    const { data: existingLink, error: existingError } = await supabase
      .from("tracking_links")
      .select("token")
      .eq("idempotency_key", payload.idempotencyKey)
      .maybeSingle();

    if (existingError) {
      throw existingError;
    }

    if (existingLink?.token) {
      return NextResponse.json(
        {
          token: existingLink.token,
          trackedUrl: buildTrackedUrl(baseUrl, existingLink.token),
          reused: true,
        },
        { status: 200 }
      );
    }

    const token = createTrackingToken();
    const { error: insertError } = await supabase.from("tracking_links").insert(
      {
        token,
        idempotency_key: payload.idempotencyKey,
        target_url: payload.targetUrl,
        deal_id: payload.dealId,
        queue_item_id: payload.queueItemId,
        platform: payload.platform,
        destination_key: payload.destinationKey,
        source_group: payload.sourceGroup,
        post_variant: payload.postVariant,
        metadata: payload.metadata ?? {},
      }
    );

    if (insertError?.code === "23505") {
      const { data: racedLink, error: racedLookupError } = await supabase
        .from("tracking_links")
        .select("token")
        .eq("idempotency_key", payload.idempotencyKey)
        .maybeSingle();

      if (racedLookupError) {
        throw racedLookupError;
      }

      if (racedLink?.token) {
        return NextResponse.json(
          {
            token: racedLink.token,
            trackedUrl: buildTrackedUrl(baseUrl, racedLink.token),
            reused: true,
          },
          { status: 200 }
        );
      }
    }

    if (insertError) {
      throw insertError;
    }

    return NextResponse.json(
      {
        token,
        trackedUrl: buildTrackedUrl(baseUrl, token),
        reused: false,
      },
      { status: 201 }
    );
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Failed to create tracking link";
    const status = message.startsWith("Missing required environment variable")
      ? 500
      : 400;

    return NextResponse.json({ error: message }, { status });
  }
}
