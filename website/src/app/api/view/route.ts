import { createClient } from "@supabase/supabase-js";
import { NextRequest, NextResponse } from "next/server";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export async function POST(request: NextRequest) {
  try {
    const { path } = await request.json();
    const pagePath = typeof path === "string" ? path.slice(0, 100) : "/";
    const today = new Date().toISOString().split("T")[0];

    // Upsert: increment views if exists, insert with 1 if not
    await supabase.rpc("increment_page_view", {
      view_date: today,
      view_path: pagePath,
    });

    return NextResponse.json({ ok: true });
  } catch {
    return NextResponse.json({ ok: true });
  }
}
