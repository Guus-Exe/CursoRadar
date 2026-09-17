"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AlertTriangle, CheckCircle2, Search, Bug, ChevronDown, ChevronRight } from "lucide-react";

interface SystemErrorLog {
  id: string;
  component: string;
  error_type: string;
  message: string;
  stack_trace: string | null;
  resolved: boolean;
  created_at: string;
}

const INITIAL_ERRORS: SystemErrorLog[] = [
  {
    id: "err-01",
    component: "EducationProvider.SenacSP",
    error_type: "HTTPStatusError",
    message: "HTTP 502 Bad Gateway ao consultar catálogo da unidade Campinas",
    stack_trace: "httpx.HTTPStatusError: Server error '502 Bad Gateway' for url 'https://www.sp.senac.br/...'\n  File 'senac.py', line 124, in get_offer_state\n    res.raise_for_status()",
    resolved: true,
    created_at: "2026-09-16T04:12:00Z",
  },
  {
    id: "err-02",
    component: "TelegramNotifier",
    error_type: "ForbiddenError",
    message: "Bot foi bloqueado pelo usuário com chat_id=12398471",
    stack_trace: "telegram.error.Forbidden: Bot was blocked by the user\n  File 'telegram.py', line 89, in send_to_user",
    resolved: true,
    created_at: "2026-09-15T18:30:12Z",
  },
];

export default function AdminErrorsPage() {
  const [errors] = useState<SystemErrorLog[]>(INITIAL_ERRORS);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const filtered = errors.filter(
    (e) =>
      e.component.toLowerCase().includes(search.toLowerCase()) ||
      e.message.toLowerCase().includes(search.toLowerCase()) ||
      e.error_type.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <AlertTriangle className="h-7 w-7 text-rose-600" />
            Logs de Erros do Sistema
          </h1>
          <p className="text-slate-500 mt-1">
            Registro detalhado de falhas de raspagem, falhas de envio de alertas e exceções não tratadas.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Buscar por componente ou mensagem..."
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
                <TableHead className="w-8"></TableHead>
                <TableHead>Componente</TableHead>
                <TableHead>Tipo de Erro</TableHead>
                <TableHead>Mensagem</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Horário</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((err) => {
                const isExpanded = expandedId === err.id;
                return (
                  <>
                    <TableRow
                      key={err.id}
                      className="cursor-pointer hover:bg-slate-50"
                      onClick={() => setExpandedId(isExpanded ? null : err.id)}
                    >
                      <TableCell>
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4 text-slate-400" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-slate-400" />
                        )}
                      </TableCell>
                      <TableCell className="font-mono text-xs font-semibold text-slate-700">
                        {err.component}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-rose-700 bg-rose-50 border-rose-200 text-xs">
                          {err.error_type}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-slate-800 max-w-md truncate">
                        {err.message}
                      </TableCell>
                      <TableCell>
                        {err.resolved ? (
                          <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300">
                            <CheckCircle2 className="h-3 w-3 mr-1 inline" /> RESOLVIDO
                          </Badge>
                        ) : (
                          <Badge className="bg-rose-100 text-rose-800 border-rose-300">
                            ABERTO
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right text-xs text-slate-500 font-mono">
                        {new Date(err.created_at).toLocaleDateString("pt-BR", {
                          day: "2-digit",
                          month: "short",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </TableCell>
                    </TableRow>
                    {isExpanded && err.stack_trace && (
                      <TableRow key={`${err.id}-stack`} className="bg-slate-900 text-slate-100">
                        <TableCell colSpan={6} className="p-4 font-mono text-xs whitespace-pre-wrap leading-relaxed">
                          <div className="text-slate-400 mb-1 text-[11px] uppercase font-bold">Stack Trace:</div>
                          {err.stack_trace}
                        </TableCell>
                      </TableRow>
                    )}
                  </>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
