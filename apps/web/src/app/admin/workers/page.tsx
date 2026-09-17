"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Activity, Server, RefreshCw, Cpu, CheckCircle2, Clock } from "lucide-react";

interface WorkerHeartbeat {
  id: string;
  worker_id: string;
  hostname: string;
  status: "HEALTHY" | "DEGRADED" | "OFFLINE";
  offers_tracked: number;
  cycle_duration_seconds: number;
  last_heartbeat_at: string;
  version: string;
}

const INITIAL_WORKERS: WorkerHeartbeat[] = [
  {
    id: "w-01",
    worker_id: "worker-primary-sp1",
    hostname: "monitor-worker-prod-01",
    status: "HEALTHY",
    offers_tracked: 45,
    cycle_duration_seconds: 4.82,
    last_heartbeat_at: new Date(Date.now() - 10 * 1000).toISOString(),
    version: "2.0.0-multiuser",
  },
  {
    id: "w-02",
    worker_id: "worker-backup-sp2",
    hostname: "monitor-worker-standby",
    status: "HEALTHY",
    offers_tracked: 45,
    cycle_duration_seconds: 0.12,
    last_heartbeat_at: new Date(Date.now() - 25 * 1000).toISOString(),
    version: "2.0.0-multiuser",
  },
];

export default function AdminWorkersPage() {
  const [workers, setWorkers] = useState<WorkerHeartbeat[]>(INITIAL_WORKERS);
  const [refreshing, setRefreshing] = useState(false);

  function handleTriggerScan() {
    setRefreshing(true);
    setTimeout(() => {
      setRefreshing(false);
      setWorkers((prev) =>
        prev.map((w) => ({
          ...w,
          last_heartbeat_at: new Date().toISOString(),
        }))
      );
    }, 1200);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <Activity className="h-7 w-7 text-purple-600" />
            Saúde dos Workers de Monitoramento
          </h1>
          <p className="text-slate-500 mt-1">
            Telemetria em tempo real das instâncias Python responsáveis pela varredura contínua.
          </p>
        </div>
        <Button
          onClick={handleTriggerScan}
          disabled={refreshing}
          className="bg-purple-600 hover:bg-purple-700 text-white"
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Sincronizando..." : "Solicitar Heartbeat Imediato"}
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <Card className="border-emerald-200 bg-emerald-50/40">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-emerald-800">
              Taxa de Uptime dos Workers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-emerald-900">99.98%</div>
            <p className="text-xs text-emerald-700 mt-1">Nenhuma interrupção nos últimos 30 dias</p>
          </CardContent>
        </Card>

        <Card className="border-indigo-200 bg-indigo-50/40">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-indigo-800">
              Duração Média do Ciclo
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-indigo-900">4.8 s</div>
            <p className="text-xs text-indigo-700 mt-1">Intervalo de varredura: a cada 60s</p>
          </CardContent>
        </Card>

        <Card className="border-purple-200 bg-purple-50/40">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-purple-800">
              Volume de Checagens Diárias
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-purple-900">64.800</div>
            <p className="text-xs text-purple-700 mt-1">Com proteção contra ban de IP e backoff</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Identificador do Worker</TableHead>
                <TableHead>Hostname / Servidor</TableHead>
                <TableHead>Versão</TableHead>
                <TableHead>Ofertas Rastreadas</TableHead>
                <TableHead>Duração do Ciclo</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Último Heartbeat</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {workers.map((worker) => (
                <TableRow key={worker.id}>
                  <TableCell className="font-semibold text-slate-900 flex items-center gap-2">
                    <Server className="h-4 w-4 text-purple-600" />
                    {worker.worker_id}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-slate-600">
                    {worker.hostname}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="font-mono text-[11px]">
                      {worker.version}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-semibold text-slate-800">
                    {worker.offers_tracked} ofertas
                  </TableCell>
                  <TableCell className="text-slate-700">
                    {worker.cycle_duration_seconds}s
                  </TableCell>
                  <TableCell>
                    <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300">
                      <CheckCircle2 className="h-3 w-3 mr-1 inline" /> {worker.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right text-xs text-slate-500 font-mono">
                    {new Date(worker.last_heartbeat_at).toLocaleTimeString("pt-BR")}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
