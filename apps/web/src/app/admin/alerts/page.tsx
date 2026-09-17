"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Bell, Search, Send, CheckCircle2, ShieldCheck } from "lucide-react";

interface AdminAlertLog {
  id: string;
  user_email: string;
  course_title: string;
  trigger_reason: string;
  channel: "TELEGRAM" | "EMAIL";
  fingerprint: string;
  status: "DELIVERED" | "PENDING" | "FAILED";
  created_at: string;
}

const INITIAL_ALERTS: AdminAlertLog[] = [
  {
    id: "alt-01",
    user_email: "carlos.silva@gmail.com",
    course_title: "Técnico em Desenvolvimento de Sistemas",
    trigger_reason: "2 novas bolsas abertas",
    channel: "TELEGRAM",
    fingerprint: "e3b0c44298fc1c149afbf4c8996fb924",
    status: "DELIVERED",
    created_at: "2026-09-17T10:14:20Z",
  },
  {
    id: "alt-02",
    user_email: "juliana.costa@gmail.com",
    course_title: "Técnico em Desenvolvimento de Sistemas",
    trigger_reason: "2 novas bolsas abertas",
    channel: "TELEGRAM",
    fingerprint: "7d793037a0760186574b0282f2f435e7",
    status: "DELIVERED",
    created_at: "2026-09-17T10:14:21Z",
  },
  {
    id: "alt-03",
    user_email: "mariana.oliveira@outlook.com",
    course_title: "Técnico em Administração",
    trigger_reason: "Turma aberta para matrículas",
    channel: "TELEGRAM",
    fingerprint: "5e884898da28047151d0e56f8dc62927",
    status: "DELIVERED",
    created_at: "2026-09-16T15:22:10Z",
  },
];

export default function AdminAlertsPage() {
  const [alerts] = useState<AdminAlertLog[]>(INITIAL_ALERTS);
  const [search, setSearch] = useState("");

  const filtered = alerts.filter(
    (a) =>
      a.course_title.toLowerCase().includes(search.toLowerCase()) ||
      a.user_email.toLowerCase().includes(search.toLowerCase()) ||
      a.trigger_reason.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <Bell className="h-7 w-7 text-purple-600" />
            Alertas Emitidos
          </h1>
          <p className="text-slate-500 mt-1">
            Log consolidado de notificações despachadas para usuários via Telegram.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Buscar por usuário, curso ou motivo..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Destinatário</TableHead>
                <TableHead>Curso</TableHead>
                <TableHead>Gatilho / Motivo</TableHead>
                <TableHead>Canal</TableHead>
                <TableHead>Fingerprint SHA256</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Horário</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((alert) => (
                <TableRow key={alert.id}>
                  <TableCell className="font-medium text-slate-900">
                    {alert.user_email}
                  </TableCell>
                  <TableCell className="font-medium text-slate-900">
                    {alert.course_title}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-slate-700 bg-slate-50">
                      {alert.trigger_reason}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <span className="flex items-center text-xs font-semibold text-sky-600">
                      <Send className="h-3 w-3 mr-1" /> Telegram
                    </span>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-slate-500">
                    {alert.fingerprint.slice(0, 12)}...
                  </TableCell>
                  <TableCell>
                    <Badge className="bg-emerald-100 text-emerald-800 border-emerald-200">
                      <CheckCircle2 className="h-3 w-3 mr-1 inline" /> ENTREGUE
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right text-xs text-slate-500">
                    {new Date(alert.created_at).toLocaleTimeString("pt-BR", {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    })}
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
