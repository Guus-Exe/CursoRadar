"use client";

import { useState } from "react";
import { Bell, ExternalLink, Filter, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface AlertItem {
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

const SAMPLE_ALERTS: AlertItem[] = [
  {
    id: "alt-1",
    type: "bolsa",
    title: "Bolsa de Estudo (PSG) 100% Gratuita Disponível!",
    course: "Técnico em Modelagem do Vestuário",
    unit: "Senac Lapa Faustolo",
    shift: "Noturno",
    time: "Hoje às 14:32",
    delivered: true,
    channel: "Telegram (@gustavo)",
    url: "https://www.sp.senac.br/senac-lapa-faustolo/cursos-tecnicos/curso-tecnico-em-modelagem-do-vestuario?bolsa=true&oferta=9900357333",
    details: "Vagas liberadas para inscrição imediata pelo Programa Senac de Gratuidade.",
  },
  {
    id: "alt-2",
    type: "turma",
    title: "Nova Turma Detectada para Outubro/2026",
    course: "Técnico em Modelagem do Vestuário",
    unit: "Senac Lapa Faustolo",
    shift: "Noturno",
    time: "Ontem às 18:15",
    delivered: true,
    channel: "Telegram (@gustavo)",
    url: "https://www.sp.senac.br/senac-lapa-faustolo/cursos-tecnicos/curso-tecnico-em-modelagem-do-vestuario?bolsa=true&oferta=9900360124",
    details: "Nova oferta 9900360124 lançada no portal oficial do Senac.",
  },
  {
    id: "alt-3",
    type: "vaga",
    title: "Matrículas Regulares Liberadas (Desistência)",
    course: "Técnico em Modelagem do Vestuário",
    unit: "Senac Lapa Faustolo",
    shift: "Noturno",
    time: "15/09/2026 às 11:05",
    delivered: true,
    channel: "Telegram (@gustavo)",
    url: "https://www.sp.senac.br/senac-lapa-faustolo/cursos-tecnicos/curso-tecnico-em-modelagem-do-vestuario?bolsa=true&oferta=9900357333",
    details: "Botão 'Comprar curso' liberado com vagas remanescentes.",
  },
];

export default function AlertsHistoryPage() {
  const [filter, setFilter] = useState<"all" | "bolsa" | "vaga" | "turma">("all");

  const filteredAlerts = SAMPLE_ALERTS.filter((a) => {
    if (filter === "all") return true;
    return a.type === filter;
  });

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
            Todos ({SAMPLE_ALERTS.length})
          </Button>
          <Button
            size="sm"
            variant={filter === "bolsa" ? "default" : "outline"}
            onClick={() => setFilter("bolsa")}
            className="text-xs"
          >
            🎓 Bolsas
          </Button>
          <Button
            size="sm"
            variant={filter === "vaga" ? "default" : "outline"}
            onClick={() => setFilter("vaga")}
            className="text-xs"
          >
            💳 Vagas Pagas
          </Button>
          <Button
            size="sm"
            variant={filter === "turma" ? "default" : "outline"}
            onClick={() => setFilter("turma")}
            className="text-xs"
          >
            🆕 Novas Turmas
          </Button>
        </div>
      </div>

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
                <p className="text-sm text-slate-600">{alert.details}</p>

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
                    Inscrever-se no Senac <ExternalLink className="h-3.5 w-3.5" />
                  </Button>
                </a>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
