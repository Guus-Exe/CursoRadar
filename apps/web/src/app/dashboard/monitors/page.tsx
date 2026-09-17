"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  PlusCircle,
  Pause,
  Play,
  Trash2,
  AlertTriangle,
  Building2,
  MapPin,
  Laptop,
  Clock,
  GraduationCap,
  Calendar,
  Send,
  Loader2,
  RefreshCw,
  Search,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { createClient } from "@/lib/supabase/client";

interface ProviderJoined {
  name: string;
  slug: string;
}

interface MonitorProviderJoined {
  provider_id: string;
  providers: ProviderJoined | null;
}

interface MonitorRecord {
  id: string;
  user_id: string;
  query_text: string | null;
  all_providers: boolean;
  city: string | null;
  state: string;
  modality: string;
  opportunity_type: string;
  shift: string | null;
  active: boolean;
  notify_channels: string[];
  created_at: string;
  updated_at: string;
  monitor_providers?: MonitorProviderJoined[];
}

export default function MonitorsPage() {
  const router = useRouter();
  const [monitors, setMonitors] = useState<MonitorRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Status toggle & Delete state
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<MonitorRecord | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchMonitors = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const supabase = createClient();
      const {
        data: { user },
        error: userError,
      } = await supabase.auth.getUser();

      if (userError || !user) {
        router.push("/login");
        return;
      }

      const { data, error: fetchError } = await supabase
        .from("monitors")
        .select("*, monitor_providers(provider_id, providers(name, slug))")
        .order("created_at", { ascending: false });

      if (fetchError) {
        console.error("Erro ao carregar monitores:", fetchError);
        setError("Não foi possível carregar os monitoramentos.");
        return;
      }

      setMonitors((data as unknown as MonitorRecord[]) || []);
    } catch (err: any) {
      console.error("Exceção ao buscar monitores:", err);
      setError("Erro inesperado ao consultar o banco de dados.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    fetchMonitors();
  }, [fetchMonitors]);

  async function toggleStatus(id: string, currentActive: boolean) {
    setTogglingId(id);
    try {
      const supabase = createClient();
      const { error: updateError } = await supabase
        .from("monitors")
        .update({ active: !currentActive })
        .eq("id", id);

      if (updateError) {
        console.error("Erro ao atualizar monitor:", updateError);
        alert("Erro ao alterar o status do monitoramento.");
        return;
      }

      setMonitors((prev) =>
        prev.map((m) => (m.id === id ? { ...m, active: !currentActive } : m))
      );
    } catch (err) {
      console.error("Exceção ao alternar status:", err);
    } finally {
      setTogglingId(null);
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setDeleting(true);

    try {
      const supabase = createClient();
      const { error: delError } = await supabase
        .from("monitors")
        .delete()
        .eq("id", deleteTarget.id);

      if (delError) {
        console.error("Erro ao excluir monitor:", delError);
        alert("Erro ao excluir o monitoramento.");
        return;
      }

      setMonitors((prev) => prev.filter((m) => m.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err) {
      console.error("Exceção ao excluir monitor:", err);
    } finally {
      setDeleting(false);
    }
  }

  // Format Helpers
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
        return "🎓 Bolsa PSG (100% Grátis)";
      case "gratuito":
        return "🆓 Gratuito";
      case "pago":
        return "💳 Curso Pago";
      case "all":
      default:
        return "✨ Todas as vagas";
    }
  }

  function formatShift(shift: string | null) {
    if (!shift || shift === "qualquer") return "Qualquer turno";
    return shift;
  }

  function formatDate(dateStr: string) {
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

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Meus Monitoramentos
          </h1>
          <p className="text-sm text-slate-600">
            Acompanhe em tempo real as vagas, bolsas e novas turmas nas plataformas cadastradas.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchMonitors}
            disabled={loading}
            className="gap-1.5 text-slate-600"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Atualizar
          </Button>
          <Link href="/dashboard/monitors/new">
            <Button className="gap-1.5 shadow-sm">
              <PlusCircle className="h-4 w-4" />
              Novo Monitoramento
            </Button>
          </Link>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-600" />
            <span>{error}</span>
          </div>
          <Button variant="outline" size="sm" onClick={fetchMonitors} className="text-xs">
            Tentar novamente
          </Button>
        </div>
      )}

      {/* Loading state */}
      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((n) => (
            <Card key={n} className="animate-pulse p-6">
              <div className="space-y-3">
                <div className="h-5 w-1/3 bg-slate-200 rounded" />
                <div className="h-4 w-1/2 bg-slate-100 rounded" />
                <div className="flex gap-2 pt-2">
                  <div className="h-6 w-20 bg-slate-200 rounded-full" />
                  <div className="h-6 w-24 bg-slate-200 rounded-full" />
                  <div className="h-6 w-16 bg-slate-200 rounded-full" />
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : monitors.length === 0 ? (
        /* Empty State */
        <Card className="text-center py-16 border-dashed border-2 border-slate-200">
          <CardContent className="space-y-4 max-w-md mx-auto">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-blue-50 text-blue-600">
              <Search className="h-7 w-7" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900">
                Nenhum monitoramento ativo
              </h3>
              <p className="text-sm text-slate-500 mt-1">
                Você ainda não configurou nenhum alerta de curso. Crie seu primeiro monitoramento para ser avisado assim que vagas ou bolsas abrirem!
              </p>
            </div>
            <div className="pt-2">
              <Link href="/dashboard/monitors/new">
                <Button size="lg" className="gap-2 shadow-sm font-semibold">
                  <PlusCircle className="h-5 w-5" />
                  Criar Primeiro Monitoramento
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      ) : (
        /* Monitors List */
        <div className="grid grid-cols-1 gap-4">
          {monitors.map((mon) => (
            <Card
              key={mon.id}
              className={`overflow-hidden transition-all border ${
                mon.active
                  ? "border-slate-200 hover:border-slate-300 shadow-sm"
                  : "border-slate-200 bg-slate-50/60 opacity-80"
              }`}
            >
              <div className="p-5 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="space-y-3 flex-1">
                  {/* Title & Status */}
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-lg font-bold text-slate-900">
                      {mon.query_text || "Busca Geral"}
                    </h2>
                    {mon.active ? (
                      <Badge variant="success" className="gap-1">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-600 animate-pulse" />
                        Monitorando Ativamente
                      </Badge>
                    ) : (
                      <Badge variant="secondary">Pausado</Badge>
                    )}
                  </div>

                  {/* Provider Badges */}
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-xs text-slate-500 flex items-center gap-1">
                      <Building2 className="h-3.5 w-3.5 text-slate-400" />
                      Provedores:
                    </span>
                    {mon.all_providers ? (
                      <Badge variant="default" className="bg-blue-600 text-white text-xs">
                        Todas as plataformas
                      </Badge>
                    ) : mon.monitor_providers && mon.monitor_providers.length > 0 ? (
                      mon.monitor_providers.map((mp) => (
                        <Badge
                          key={mp.provider_id}
                          variant="outline"
                          className="bg-white border-blue-200 text-blue-800 text-xs font-medium"
                        >
                          {mp.providers?.name || "Senac São Paulo"}
                        </Badge>
                      ))
                    ) : (
                      <Badge variant="outline" className="text-xs">
                        Senac São Paulo
                      </Badge>
                    )}
                  </div>

                  {/* Filters & Preferences Badges */}
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    {/* Location */}
                    <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2.5 py-1 font-medium text-slate-700">
                      <MapPin className="h-3.5 w-3.5 text-slate-500" />
                      {mon.city ? `${mon.city} - ${mon.state}` : `Todas as cidades (${mon.state})`}
                    </span>

                    {/* Modality */}
                    <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2.5 py-1 font-medium text-slate-700">
                      <Laptop className="h-3.5 w-3.5 text-slate-500" />
                      {formatModality(mon.modality)}
                    </span>

                    {/* Shift */}
                    <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2.5 py-1 font-medium text-slate-700">
                      <Clock className="h-3.5 w-3.5 text-slate-500" />
                      {formatShift(mon.shift)}
                    </span>

                    {/* Opportunity Type */}
                    <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2.5 py-1 font-medium text-slate-700">
                      <GraduationCap className="h-3.5 w-3.5 text-slate-500" />
                      {formatOpportunity(mon.opportunity_type)}
                    </span>
                  </div>

                  {/* Footer Meta: Channels & Date */}
                  <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400 pt-1">
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      Criado em {formatDate(mon.created_at)}
                    </span>
                    {mon.notify_channels?.includes("telegram") && (
                      <span className="flex items-center gap-1 text-sky-600 font-medium">
                        <Send className="h-3 w-3" />
                        Avisos via Telegram
                      </span>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex sm:flex-col items-center sm:items-end gap-2 shrink-0 pt-2 sm:pt-0">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => toggleStatus(mon.id, mon.active)}
                    disabled={togglingId === mon.id}
                    className="gap-1.5 text-xs w-full sm:w-28"
                  >
                    {togglingId === mon.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : mon.active ? (
                      <>
                        <Pause className="h-3.5 w-3.5 text-amber-600" />
                        Pausar
                      </>
                    ) : (
                      <>
                        <Play className="h-3.5 w-3.5 text-emerald-600" />
                        Retomar
                      </>
                    )}
                  </Button>

                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setDeleteTarget(mon)}
                    className="gap-1.5 text-xs w-full sm:w-28 border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700"
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

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <DialogHeader>
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-red-600 mb-2">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <DialogTitle className="text-center">Confirmar Exclusão</DialogTitle>
          <DialogDescription className="text-center">
            Tem certeza de que deseja excluir o monitoramento de{" "}
            <strong className="text-slate-900 font-semibold">
              &quot;{deleteTarget?.query_text || "este curso"}&quot;
            </strong>
            ? Você deixará de receber alertas sobre novas vagas e bolsas desta busca.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setDeleteTarget(null)}
            disabled={deleting}
          >
            Cancelar
          </Button>
          <Button
            variant="destructive"
            onClick={confirmDelete}
            disabled={deleting}
            className="gap-1.5"
          >
            {deleting && <Loader2 className="h-4 w-4 animate-spin" />}
            Sim, Excluir Monitoramento
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
