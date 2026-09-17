"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { PlusCircle, Pause, Play, Trash2, ExternalLink, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";

interface MonitorItem {
  id: string;
  course: string;
  institution: string;
  unit: string;
  shift: string;
  active: boolean;
  notifyScholarship: boolean;
  notifyPaid: boolean;
  notifyNewOffer: boolean;
  lastChecked: string;
  url: string;
}

const DEFAULT_MONITORS: MonitorItem[] = [
  {
    id: "mon-1",
    course: "Técnico em Modelagem do Vestuário",
    institution: "Senac São Paulo",
    unit: "Senac Lapa Faustolo",
    shift: "Noturno",
    active: true,
    notifyScholarship: true,
    notifyPaid: true,
    notifyNewOffer: true,
    lastChecked: "Hoje às 14:35",
    url: "https://www.sp.senac.br/senac-lapa-faustolo/cursos-tecnicos/curso-tecnico-em-modelagem-do-vestuario?bolsa=true&oferta=9900357333",
  },
];

export default function MonitorsPage() {
  const [monitors, setMonitors] = useState<MonitorItem[]>(DEFAULT_MONITORS);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  useEffect(() => {
    const raw = localStorage.getItem("senac_user_monitors");
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setMonitors(parsed);
        }
      } catch {}
    }
  }, []);

  function saveMonitors(updated: MonitorItem[]) {
    setMonitors(updated);
    localStorage.setItem("senac_user_monitors", JSON.stringify(updated));
  }

  function toggleStatus(id: string) {
    const updated = monitors.map((m) =>
      m.id === id ? { ...m, active: !m.active } : m
    );
    saveMonitors(updated);
  }

  function confirmDelete() {
    if (deleteTargetId) {
      const updated = monitors.filter((m) => m.id !== deleteTargetId);
      saveMonitors(updated);
      setDeleteTargetId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Meus Monitoramentos
          </h1>
          <p className="text-sm text-slate-600">
            Gerencie os cursos, unidades e turnos que o sistema está monitorando para você.
          </p>
        </div>
        <Link href="/dashboard/monitors/new">
          <Button className="gap-1.5 shadow-sm">
            <PlusCircle className="h-4 w-4" />
            Novo Monitoramento
          </Button>
        </Link>
      </div>

      {monitors.length === 0 ? (
        <Card className="text-center py-12">
          <CardContent>
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 text-blue-600 mb-4">
              <PlusCircle className="h-6 w-6" />
            </div>
            <h3 className="text-lg font-semibold text-slate-900">Nenhum monitoramento cadastrado</h3>
            <p className="text-sm text-slate-500 mt-1 max-w-sm mx-auto">
              Você ainda não está monitorando nenhum curso. Cadastre seu primeiro interesse agora!
            </p>
            <div className="mt-6">
              <Link href="/dashboard/monitors/new">
                <Button>Criar Monitoramento</Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {monitors.map((mon) => (
            <Card key={mon.id} className="overflow-hidden">
              <div className="p-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-lg font-bold text-slate-900">{mon.course}</h2>
                    <Badge variant="outline" className="font-semibold">
                      {mon.shift}
                    </Badge>
                    {mon.active ? (
                      <Badge variant="success">Monitorando Ativamente</Badge>
                    ) : (
                      <Badge variant="secondary">Pausado</Badge>
                    )}
                  </div>

                  <p className="text-sm text-slate-600">
                    {mon.institution} • <strong className="text-slate-800">{mon.unit}</strong>
                  </p>

                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 pt-1">
                    <span>Preferências:</span>
                    {mon.notifyScholarship && (
                      <span className="rounded bg-slate-100 px-2 py-0.5 text-slate-700">🎓 Bolsas (PSG)</span>
                    )}
                    {mon.notifyPaid && (
                      <span className="rounded bg-slate-100 px-2 py-0.5 text-slate-700">💳 Vagas Pagas</span>
                    )}
                    {mon.notifyNewOffer && (
                      <span className="rounded bg-slate-100 px-2 py-0.5 text-slate-700">🆕 Novas Turmas</span>
                    )}
                    <span className="text-slate-400">• Checado: {mon.lastChecked}</span>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 pt-2 sm:pt-0">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => toggleStatus(mon.id)}
                    className="gap-1.5 text-xs"
                  >
                    {mon.active ? (
                      <>
                        <Pause className="h-3.5 w-3.5 text-amber-600" />
                        Pausar
                      </>
                    ) : (
                      <>
                        <Play className="h-3.5 w-3.5 text-emerald-600" />
                        Reativar
                      </>
                    )}
                  </Button>

                  <a href={mon.url} target="_blank" rel="noreferrer">
                    <Button size="sm" variant="outline" className="gap-1 text-xs">
                      <ExternalLink className="h-3.5 w-3.5" />
                      Página Oficial
                    </Button>
                  </a>

                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setDeleteTargetId(mon.id)}
                    className="gap-1 text-xs border-red-200 text-red-600 hover:bg-red-50"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Excluir
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Confirmation Dialog for Deletion */}
      <Dialog open={deleteTargetId !== null} onOpenChange={(open) => !open && setDeleteTargetId(null)}>
        <DialogHeader>
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-red-600 mb-2">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <DialogTitle className="text-center">Confirmar Exclusão</DialogTitle>
          <DialogDescription className="text-center">
            Tem certeza de que deseja excluir este monitoramento? Você deixará de receber alertas sobre novas vagas e bolsas deste curso.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setDeleteTargetId(null)}>
            Cancelar
          </Button>
          <Button variant="destructive" onClick={confirmDelete}>
            Sim, Excluir
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
