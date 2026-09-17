"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Eye,
  Bell,
  Send,
  CheckCircle2,
  AlertCircle,
  PlusCircle,
  ArrowRight,
  ExternalLink,
  Building2,
  MapPin,
  Laptop,
  Clock,
  GraduationCap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { createClient } from "@/lib/supabase/client";

interface ProviderJoined {
  name: string;
  slug: string;
}

interface MonitorProviderJoined {
  provider_id: string;
  providers: ProviderJoined | null;
}

interface MonitorItem {
  id: string;
  query_text: string | null;
  all_providers: boolean;
  city: string | null;
  state: string;
  modality: string;
  opportunity_type: string;
  shift: string | null;
  active: boolean;
  created_at: string;
  monitor_providers?: MonitorProviderJoined[];
}

interface AlertItem {
  id: string;
  alert_type: string;
  message_content: string;
  sent_at: string;
  channel: string;
  delivered: boolean;
}

export default function DashboardPage() {
  const [telegramConnected, setTelegramConnected] = useState<boolean>(false);
  const [telegramUsername, setTelegramUsername] = useState<string | null>(null);
  const [monitorsCount, setMonitorsCount] = useState<number>(0);
  const [alertsCount, setAlertsCount] = useState<number>(0);
  const [monitors, setMonitors] = useState<MonitorItem[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadDashboardData() {
      setLoading(true);
      try {
        const supabase = createClient();
        const {
          data: { user },
        } = await supabase.auth.getUser();

        if (!user) {
          setLoading(false);
          return;
        }

        // 1. Contagem de monitores ativos do usuário
        const { count: activeCount } = await supabase
          .from("monitors")
          .select("*", { count: "exact", head: true })
          .eq("active", true);

        setMonitorsCount(activeCount || 0);

        // 2. Contagem de alertas recebidos
        const { count: totalAlerts } = await supabase
          .from("alerts")
          .select("*", { count: "exact", head: true });

        setAlertsCount(totalAlerts || 0);

        // 3. Status de vinculação do Telegram
        const { data: tgAccount } = await supabase
          .from("telegram_accounts")
          .select("telegram_username, active")
          .eq("active", true)
          .maybeSingle();

        if (tgAccount && tgAccount.active) {
          setTelegramConnected(true);
          setTelegramUsername(tgAccount.telegram_username || null);
        } else {
          setTelegramConnected(false);
          setTelegramUsername(null);
        }

        // 4. Monitores recentes do usuário
        const { data: monitorList } = await supabase
          .from("monitors")
          .select("*, monitor_providers(provider_id, providers(name, slug))")
          .order("created_at", { ascending: false })
          .limit(3);

        setMonitors((monitorList as unknown as MonitorItem[]) || []);

        // 5. Alertas recentes
        const { data: alertList } = await supabase
          .from("alerts")
          .select("*")
          .order("sent_at", { ascending: false })
          .limit(3);

        setAlerts((alertList as unknown as AlertItem[]) || []);
      } catch (err) {
        console.error("Erro ao carregar dados do dashboard:", err);
      } finally {
        setLoading(false);
      }
    }

    loadDashboardData();
  }, []);

  function formatModality(m: string) {
    switch (m) {
      case "presencial":
        return "Presencial";
      case "online":
        return "Online / EaD";
      case "hibrido":
        return "Híbrido";
      case "all":
      default:
        return "Todas as modalidades";
    }
  }

  function formatOpportunity(opp: string) {
    switch (opp) {
      case "bolsa":
        return "🎓 Bolsa PSG";
      case "gratuito":
        return "🆓 Gratuito";
      case "pago":
        return "💳 Pago";
      case "all":
      default:
        return "✨ Todas";
    }
  }

  function formatTime(dateStr: string) {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  }

  return (
    <div className="space-y-8">
      {/* Page Title & Action */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Visão Geral
          </h1>
          <p className="text-sm text-slate-600">
            Acompanhe o estado das suas buscas, alertas recentes e canais de notificação.
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/dashboard/monitors/new">
            <Button className="gap-1.5 shadow-sm">
              <PlusCircle className="h-4 w-4" />
              Novo Monitoramento
            </Button>
          </Link>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-600">
              Monitoramentos Ativos
            </CardTitle>
            <Eye className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-900">
              {loading ? "..." : monitorsCount}
            </div>
            <p className="text-xs text-slate-500 mt-1">Buscas ativas sendo verificadas</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-600">
              Alertas Recebidos
            </CardTitle>
            <Bell className="h-4 w-4 text-emerald-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-900">
              {loading ? "..." : alertsCount}
            </div>
            <p className="text-xs text-slate-500 mt-1">Oportunidades notificadas</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-600">
              Canal Telegram
            </CardTitle>
            <Send className="h-4 w-4 text-sky-500" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {telegramConnected ? (
                <>
                  <Badge variant="success" className="gap-1">
                    <CheckCircle2 className="h-3 w-3" /> Conectado
                  </Badge>
                  {telegramUsername && (
                    <span className="text-xs text-slate-500 font-mono">
                      @{telegramUsername}
                    </span>
                  )}
                </>
              ) : (
                <Badge variant="warning" className="gap-1">
                  <AlertCircle className="h-3 w-3" /> Desconectado
                </Badge>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-2">
              {telegramConnected ? (
                "Alertas ativos via bot do Telegram"
              ) : (
                <Link href="/dashboard/settings/telegram" className="text-blue-600 hover:underline">
                  Conectar conta agora →
                </Link>
              )}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-600">
              Status do Monitor
            </CardTitle>
            <div className="flex h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" />
          </CardHeader>
          <CardContent>
            <div className="text-sm font-semibold text-emerald-700">Operando Normalmente</div>
            <p className="text-xs text-slate-500 mt-1">Monitoramento automático ativo</p>
          </CardContent>
        </Card>
      </div>

      {/* Seus Monitoramentos Recentes */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Seus Monitoramentos</h2>
          <Link href="/dashboard/monitors" className="text-sm text-blue-600 hover:underline flex items-center gap-1">
            Ver todos ({monitorsCount}) <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        {monitors.length === 0 ? (
          <Card className="text-center py-10 border-dashed border-2">
            <CardContent className="space-y-3">
              <p className="text-sm text-slate-500">
                Você ainda não possui monitoramentos cadastrados no sistema.
              </p>
              <Link href="/dashboard/monitors/new">
                <Button size="sm" className="gap-1.5">
                  <PlusCircle className="h-4 w-4" />
                  Criar Primeiro Monitoramento
                </Button>
              </Link>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="p-0">
              <div className="divide-y divide-slate-200">
                {monitors.map((mon) => (
                  <div
                    key={mon.id}
                    className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-semibold text-slate-900">
                          {mon.query_text || "Busca Geral"}
                        </h3>
                        {mon.all_providers ? (
                          <Badge variant="default" className="text-[11px] bg-blue-600">
                            Todas as plataformas
                          </Badge>
                        ) : mon.monitor_providers && mon.monitor_providers.length > 0 ? (
                          mon.monitor_providers.map((mp) => (
                            <Badge key={mp.provider_id} variant="outline" className="text-[11px]">
                              {mp.providers?.name || "Senac SP"}
                            </Badge>
                          ))
                        ) : (
                          <Badge variant="outline" className="text-[11px]">
                            Senac SP
                          </Badge>
                        )}
                        {mon.active ? (
                          <Badge variant="success" className="text-[11px]">
                            Ativo
                          </Badge>
                        ) : (
                          <Badge variant="secondary" className="text-[11px]">
                            Pausado
                          </Badge>
                        )}
                      </div>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                        <span className="flex items-center gap-1">
                          <MapPin className="h-3 w-3 text-slate-400" />
                          {mon.city ? `${mon.city} - ${mon.state}` : `Todas as cidades (${mon.state})`}
                        </span>
                        <span>•</span>
                        <span>{formatModality(mon.modality)}</span>
                        <span>•</span>
                        <span>{formatOpportunity(mon.opportunity_type)}</span>
                        {mon.shift && (
                          <>
                            <span>•</span>
                            <span>{mon.shift}</span>
                          </>
                        )}
                      </div>
                    </div>
                    <div>
                      <Link href="/dashboard/monitors">
                        <Button variant="outline" size="sm" className="text-xs">
                          Gerenciar
                        </Button>
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Alertas Recentes */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Alertas Recentes</h2>
          <Link href="/dashboard/alerts" className="text-sm text-blue-600 hover:underline flex items-center gap-1">
            Histórico completo <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        {alerts.length === 0 ? (
          <Card className="text-center py-8">
            <CardContent>
              <p className="text-sm text-slate-500">
                Nenhum alerta recente gerado ainda. Seus monitoramentos verificarão novas vagas continuamente.
              </p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="p-0 divide-y divide-slate-100">
              {alerts.map((alert) => (
                <div key={alert.id} className="p-4 flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Badge variant="success" className="text-[11px]">
                        {alert.alert_type}
                      </Badge>
                      <span className="text-xs text-slate-500">
                        {formatTime(alert.sent_at)}
                      </span>
                    </div>
                    <p className="text-sm font-medium text-slate-900">
                      {alert.message_content}
                    </p>
                  </div>
                  <Link href="/dashboard/alerts">
                    <Button size="sm" variant="outline" className="text-xs shrink-0">
                      Ver Alerta
                    </Button>
                  </Link>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
