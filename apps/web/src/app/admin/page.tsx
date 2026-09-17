"use client";

import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Users,
  Eye,
  Layers,
  Bell,
  Activity,
  AlertTriangle,
  CheckCircle2,
  ArrowUpRight,
  RefreshCw,
  Server,
} from "lucide-react";

export default function AdminOverviewPage() {
  const stats = [
    { title: "Usuários Registrados", value: "148", change: "+12 este mês", icon: Users, color: "text-blue-600", bg: "bg-blue-50", href: "/admin/users" },
    { title: "Monitores Ativos", value: "312", change: "92% ativos", icon: Eye, color: "text-indigo-600", bg: "bg-indigo-50", href: "/admin/monitors" },
    { title: "Ofertas Rastreadas", value: "45", change: "1 check/minuto", icon: Layers, color: "text-purple-600", bg: "bg-purple-50", href: "/admin/offers" },
    { title: "Alertas Emitidos (24h)", value: "89", change: "100% entregues", icon: Bell, color: "text-amber-600", bg: "bg-amber-50", href: "/admin/alerts" },
    { title: "Workers Operantes", value: "2", change: "Heartbeat OK", icon: Activity, color: "text-emerald-600", bg: "bg-emerald-50", href: "/admin/workers" },
    { title: "Erros do Sistema", value: "0", change: "Nenhum erro crítico", icon: AlertTriangle, color: "text-rose-600", bg: "bg-rose-50", href: "/admin/errors" },
  ];

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Métricas & Observabilidade</h1>
          <p className="text-slate-500 mt-1">
            Status operacional, telemetria dos workers e tráfego de alertas da plataforma.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300 py-1.5 px-3">
            <span className="w-2 h-2 rounded-full bg-emerald-500 mr-2 animate-pulse" />
            Todos os Serviços Saudáveis
          </Badge>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {stats.map((s) => {
          const Icon = s.icon;
          return (
            <Link key={s.title} href={s.href} className="group">
              <Card className="hover:border-purple-300 hover:shadow-md transition-all">
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <span className="text-sm font-medium text-slate-600">{s.title}</span>
                  <div className={`p-2 rounded-lg ${s.bg}`}>
                    <Icon className={`h-5 w-5 ${s.color}`} />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-slate-900 group-hover:text-purple-700 transition-colors">
                    {s.value}
                  </div>
                  <div className="text-xs text-slate-500 mt-1 flex items-center justify-between">
                    <span>{s.change}</span>
                    <ArrowUpRight className="h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity text-purple-600" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>

      {/* Telemetry & Architecture section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Server className="h-5 w-5 text-purple-600" />
                  Saúde dos Workers de Varredura
                </CardTitle>
                <CardDescription>Instâncias ativas do scheduler Python de monitoramento</CardDescription>
              </div>
              <Link href="/admin/workers">
                <Button variant="ghost" size="sm" className="text-purple-600">Ver Todos</Button>
              </Link>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between">
              <div className="space-y-1">
                <div className="font-semibold text-sm text-slate-900 flex items-center gap-2">
                  <span>worker-primary-sp1</span>
                  <Badge variant="success" className="text-[10px] px-1.5 py-0 bg-emerald-100 text-emerald-800">ONLINE</Badge>
                </div>
                <div className="text-xs text-slate-500">
                  IP: 10.0.4.12 • Host: monitor-worker-prod-01
                </div>
                <div className="text-xs text-slate-500">
                  Último Heartbeat: há 12 segundos (Ciclo: 4.8s • 45 ofertas)
                </div>
              </div>
              <Activity className="h-6 w-6 text-emerald-500 animate-pulse" />
            </div>

            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between">
              <div className="space-y-1">
                <div className="font-semibold text-sm text-slate-900 flex items-center gap-2">
                  <span>worker-backup-sp2</span>
                  <Badge variant="success" className="text-[10px] px-1.5 py-0 bg-emerald-100 text-emerald-800">STANDBY</Badge>
                </div>
                <div className="text-xs text-slate-500">
                  IP: 10.0.4.13 • Host: monitor-worker-standby
                </div>
                <div className="text-xs text-slate-500">
                  Último Heartbeat: há 28 segundos (Standby sync)
                </div>
              </div>
              <CheckCircle2 className="h-6 w-6 text-slate-400" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Activity className="h-5 w-5 text-indigo-600" />
                  Eficiência do Deduplicador & Matching
                </CardTitle>
                <CardDescription>Resumo de economia de requisições às instituições</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg bg-indigo-50/70 border border-indigo-100 p-4 space-y-2">
              <div className="text-xs font-semibold uppercase tracking-wider text-indigo-800">
                Taxa de Deduplicação de Requisições
              </div>
              <div className="text-2xl font-bold text-indigo-900">
                85.6% de Economia de Tráfego
              </div>
              <p className="text-xs text-indigo-700">
                312 monitores configurados realizam apenas 45 requisições de rede ao portal Senac por ciclo.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 text-center">
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                <div className="text-xs text-slate-500">Fingerprints Únicos</div>
                <div className="text-xl font-bold text-slate-900 mt-1">1,420</div>
              </div>
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                <div className="text-xs text-slate-500">Alertas Repetidos Evitados</div>
                <div className="text-xl font-bold text-emerald-600 mt-1">3,892</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
