"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Eye, Bell, Send, CheckCircle2, AlertCircle, PlusCircle, ArrowRight, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function DashboardPage() {
  const [telegramConnected, setTelegramConnected] = useState<boolean>(false);
  const [monitorsCount, setMonitorsCount] = useState<number>(1);
  const [alertsCount, setAlertsCount] = useState<number>(3);

  useEffect(() => {
    // Check local storage for simulated or real state
    const tgLinked = localStorage.getItem("senac_telegram_linked");
    if (tgLinked === "true") {
      setTelegramConnected(true);
    }
    const savedMonitors = localStorage.getItem("senac_user_monitors");
    if (savedMonitors) {
      try {
        const parsed = JSON.parse(savedMonitors);
        setMonitorsCount(parsed.length);
      } catch {}
    }
  }, []);

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
            <div className="text-2xl font-bold text-slate-900">{monitorsCount}</div>
            <p className="text-xs text-slate-500 mt-1">Cursos sendo verificados continuamente</p>
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
            <div className="text-2xl font-bold text-slate-900">{alertsCount}</div>
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
                  <span className="text-xs text-slate-500 font-mono">@gustavo</span>
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
            <p className="text-xs text-slate-500 mt-1">Última checagem há menos de 3 min</p>
          </CardContent>
        </Card>
      </div>

      {/* Monitoramentos em Destaque */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Seus Monitoramentos</h2>
          <Link href="/dashboard/monitors" className="text-sm text-blue-600 hover:underline">
            Ver todos ({monitorsCount}) →
          </Link>
        </div>

        <Card>
          <CardContent className="p-0">
            <div className="divide-y divide-slate-200">
              <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-slate-900">Técnico em Modelagem do Vestuário</h3>
                    <Badge variant="secondary">Noturno</Badge>
                    <Badge variant="success">Ativo</Badge>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    Senac São Paulo • Unidade: <strong className="text-slate-700">Senac Lapa Faustolo</strong>
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Preferências: Bolsas (PSG) ✅ • Vagas pagas ✅ • Novas turmas ✅
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <a
                    href="https://www.sp.senac.br/senac-lapa-faustolo/cursos-tecnicos/curso-tecnico-em-modelagem-do-vestuario?bolsa=true&oferta=9900357333"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-slate-600 hover:text-blue-600 border border-slate-200 rounded px-2.5 py-1.5"
                  >
                    <span>Página Oficial</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Alertas Recentes */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Alertas Recentes</h2>
          <Link href="/dashboard/alerts" className="text-sm text-blue-600 hover:underline">
            Histórico completo →
          </Link>
        </div>

        <Card>
          <CardContent className="p-0 divide-y divide-slate-100">
            <div className="p-4 flex items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Badge variant="success">Bolsa Aberta</Badge>
                  <span className="text-xs text-slate-500">Hoje às 14:32</span>
                </div>
                <p className="text-sm font-medium text-slate-900">
                  Vagas para bolsa de estudo 100% gratuita liberadas para Técnico em Modelagem do Vestuário!
                </p>
                <p className="text-xs text-slate-500">
                  Unidade Lapa Faustolo • Período Noturno • Oferta 9900357333
                </p>
              </div>
              <a
                href="https://www.sp.senac.br/senac-lapa-faustolo/cursos-tecnicos/curso-tecnico-em-modelagem-do-vestuario?bolsa=true&oferta=9900357333"
                target="_blank"
                rel="noreferrer"
              >
                <Button size="sm" variant="outline" className="text-xs gap-1">
                  Abrir <ExternalLink className="h-3 w-3" />
                </Button>
              </a>
            </div>

            <div className="p-4 flex items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Badge variant="default">Nova Turma</Badge>
                  <span className="text-xs text-slate-500">Ontem às 18:15</span>
                </div>
                <p className="text-sm font-medium text-slate-900">
                  Nova oferta descoberta para início em Outubro/2026.
                </p>
                <p className="text-xs text-slate-500">
                  Unidade Lapa Faustolo • Código 9900360124
                </p>
              </div>
              <Button size="sm" variant="outline" className="text-xs gap-1">
                Ver Detalhes
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
