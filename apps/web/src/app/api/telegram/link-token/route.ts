import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import crypto from "crypto";

export async function POST() {
  try {
    const supabase = await createClient();
    const {
      data: { user },
      error: authError,
    } = await supabase.auth.getUser();

    // 1. Validação estrita de autenticação server-side
    if (authError || !user) {
      return NextResponse.json(
        { error: "Não autorizado. Faça login para vincular sua conta do Telegram." },
        { status: 401 }
      );
    }

    // 2. Geração de token criptográfico temporário (15 minutos de TTL)
    const token = crypto.randomBytes(24).toString("hex");
    const expiresAt = new Date(Date.now() + 15 * 60 * 1000).toISOString();
    const botUsername =
      process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME || "Curso_Radar_Bot";

    // 3. Persistência estrita no schema public.telegram_link_tokens do Supabase
    const { error: dbError } = await supabase.from("telegram_link_tokens").insert({
      user_id: user.id,
      token,
      expires_at: expiresAt,
    });

    if (dbError) {
      console.error("Erro ao registrar token do Telegram no Supabase:", dbError);
      return NextResponse.json(
        { error: "Falha ao registrar token de vinculação no banco de dados." },
        { status: 500 }
      );
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
    console.error("Erro interno ao gerar token do Telegram:", error);
    return NextResponse.json(
      { error: error?.message || "Internal server error" },
      { status: 500 }
    );
  }
}
