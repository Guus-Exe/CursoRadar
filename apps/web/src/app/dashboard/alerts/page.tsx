"use client";

import { useEffect, useState } from "react";
import { Bell, ExternalLink, CheckCircle2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { createClient } from "@/lib/supabase/client";

interface AlertDisplayItem {
  id: string;
  type: "bolsa" | "vaga" | "turma";
  title: string;
  course: string;
  unit: string;
  shift: string;
  time: string;
  delivered: boolean;
  channel: string;
  url: string;
  details: string;
}

export default function AlertsHistoryPage() {
  const [alerts, setAlerts] = useState<AlertDisplayItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "bolsa" | "vaga" | "turma">("all");

  useEffect(() => {
    async function loadAlerts() {
      setLoading(true);
      try {
        const supabase = createClient();
        const {
          data: { user },
        } = await supabase.auth.getUser();

        if (!user) {
          setAlerts([]);
          return;
        }

        const { data, error } = await supabase
          .from("alerts")
          .select(`
            id,
            alert_type,
            sent_at,
            delivered,
            channel,
            message_content,
            offer_id,
            offers (
              url,
              shift,
              courses ( name ),
              locations ( name )
            ),
            monitors (
              query_text,
              city,
              modality,
              shift
            )
          `)
          .eq("user_id", user.id)
          .order("sent_at", { ascending: false });

        if (error) {
          console.error("Erro ao carregar alertas:", error);
          setAlerts([]);
          return;
        }

        const items: AlertDisplayItem[] = (data || []).map((row: any) => {
          const atype = (row.alert_type || "").toUpperCase();
          let category: "bolsa" | "vaga" | "turma" = "vaga";
          let defaultTitle = "Vaga / Matrícula Liberada!";

          if (atype.includes("SCHOLARSHIP") || atype.includes("BOLSA")) {
            category = "bolsa";
            defaultTitle = "Bolsa de Estudo (PSG) 100% Gratuita Disponível!";
          } else if (atype.includes("NEW_OFFER") || atype.includes("TURMA")) {
            category = "turma";
            defaultTitle = "Nova Turma Detectada";
          }

          // Extract course and unit
          const course =
            row.offers?.courses?.name ||
            row.monitors?.query_text ||
            extractFromMessage(row.message_content, /Curso:\s*(.+)/i) ||
            "Curso Monitorado";

          const unit =
            row.offers?.locations?.name ||
            row.monitors?.city ||
            extractFromMessage(row.message_content, /(?:Unidade|📍 Unidade):\s*(.+)/i) ||
            "São Paulo";

          const shift =
            row.offers?.shift ||
            row.monitors?.shift ||
            extractFromMessage(row.message_content, /(?:Período|🌙 Período):\s*(.+)/i) ||
            "Geral";

          // Extract URL
          const url =
            row.offers?.url ||
            extractFromMessage(row.message_content, /(https?:\/\/[^\s\n]+)/i) ||
            "https://www.sp.senac.br";

          const timeFormatted = formatTime(row.sent_at);

          return {
            id: row.id,
            type: category,
            title: defaultTitle,
            course,
            unit,
            shift,
            time: timeFormatted,
            delivered: Boolean(row.delivered),
            channel: row.channel === "telegram" ? "Telegram" : row.channel,
            url,
            details: row.message_content || "Notificação de vaga monitorada.",
          };
        });

        setAlerts(items);
      } catch (err) {
        console.error("Erro inesperado ao consultar alertas:", err);
      } finally {
        setLoading(false);
      }
    }

    loadAlerts();
  }, []);

  function extractFromMessage(content: string, regex: RegExp): string | null {
    if (!content) return null;
    const match = content.match(regex);
    return match && match[1] ? match[1].trim() : null;
  }

  function formatTime(dateStr: string): string {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  }

  const filteredAlerts = alerts.filter((a) => {
    if (filter === "all") return true;
    return a.type === filter;
  });

  const countAll = alerts.length;
  const countBolsa = alerts.filter((a) => a.type === "bolsa").length;
  const countVaga = alerts.filter((a) => a.type === "vaga").length;
  const countTurma = alerts.filter((a) => a.type === "turma").length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Histórico de Alertas
          </h1>
          <p className="text-sm text-slate-600">
            Registro de todas as oportunidades detectadas e enviadas ao seu Telegram.
          </p>
        </div>

        {/* Filter Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant={filter === "all" ? "default" : "outline"}
            onClick={() => setFilter("all")}
            className="text-xs"
          >
            Todos ({countAll})
          </Button>
          <Button
            size="sm"
            variant={filter === "bolsa" ? "default" : "outline"}
            onClick={() => setFilter("bolsa")}
            className="text-xs"
          >
            🎓 Bolsas ({countBolsa})
          </Button>
          <Button
            size="sm"
            variant={filter === "vaga" ? "default" : "outline"}
            onClick={() => setFilter("vaga")}
            className="text-xs"
          >
            💳 Vagas Pagas ({countVaga})
          </Button>
          <Button
            size="sm"
            variant={filter === "turma" ? "default" : "outline"}
            onClick={() => setFilter("turma")}
            className="text-xs"
          >
            🆕 Novas Turmas ({countTurma})
          </Button>
        </div>
      </div>

      {loading ? (
        <Card className="text-center py-16">
          <CardContent className="space-y-3">
            <RefreshCw className="h-6 w-6 animate-spin mx-auto text-blue-600" />
            <p className="text-sm text-slate-500">Carregando histórico de alertas...</p>
          </CardContent>
        </Card>
      ) : filteredAlerts.length === 0 ? (
        <Card className="text-center py-16 border-dashed border-2">
          <CardContent className="space-y-3">
            <Bell className="h-8 w-8 mx-auto text-slate-400" />
            <h3 className="text-base font-semibold text-slate-800">
              Nenhum alerta encontrado
            </h3>
            <p className="text-sm text-slate-500 max-w-md mx-auto">
              Quando seus monitoramentos detectarem novas turmas, vagas ou bolsas nos cursos escolhidos, as notificações aparecerão aqui.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {filteredAlerts.map((alert) => (
            <Card key={alert.id} className="overflow-hidden">
              <div className="p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div className="space-y-1.5 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {alert.type === "bolsa" && <Badge variant="success">Bolsa Aberta</Badge>}
                    {alert.type === "turma" && <Badge variant="default">Nova Turma</Badge>}
                    {alert.type === "vaga" && <Badge variant="warning">Vaga Disponível</Badge>}
                    <span className="text-xs text-slate-500">{alert.time}</span>
                    <Badge variant="outline" className="text-[10px] gap-1">
                      <CheckCircle2 className="h-3 w-3 text-emerald-600" /> {alert.channel}
                    </Badge>
                  </div>

                  <h3 className="text-base font-bold text-slate-900">{alert.title}</h3>
                  <p className="text-sm text-slate-600 whitespace-pre-line">{alert.details}</p>

                  <div className="text-xs text-slate-500 pt-1">
                    <strong>{alert.course}</strong> • {alert.unit} • Período: {alert.shift}
                  </div>
                </div>

                <div className="flex sm:flex-col items-center gap-2 w-full sm:w-auto">
                  <a
                    href={alert.url}
                    target="_blank"
                    rel="noreferrer"
                    className="w-full sm:w-auto"
                  >
                    <Button size="sm" className="w-full gap-1 text-xs">
                      Acessar Curso <ExternalLink className="h-3.5 w-3.5" />
                    </Button>
                  </a>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
