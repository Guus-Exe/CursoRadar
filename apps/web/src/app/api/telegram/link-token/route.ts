import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import crypto from "crypto";

export async function POST() {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();

    // Fallback user ID for demo/development when auth is bypassed or previewed
    const userId = user?.id || "00000000-0000-0000-0000-000000000001";

    const token = crypto.randomBytes(24).toString("hex");
    const expiresAt = new Date(Date.now() + 15 * 60 * 1000).toISOString();
    const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME || "CursoRadarAlertsBot";

    // Attempt to persist token to database
    try {
      await supabase.from("telegram_link_tokens").insert({
        user_id: userId,
        token,
        expires_at: expiresAt,
        used: false,
      });
    } catch (dbErr) {
      console.warn("Could not save telegram link token to DB (mock mode active):", dbErr);
    }

    const linkUrl = `https://t.me/${botUsername}?start=${token}`;

    return NextResponse.json({
      success: true,
      token,
      link_url: linkUrl,
      expires_at: expiresAt,
      bot_username: botUsername,
    });
  } catch (error: any) {
    return NextResponse.json(
      { error: error?.message || "Internal server error" },
      { status: 500 }
    );
  }
}
