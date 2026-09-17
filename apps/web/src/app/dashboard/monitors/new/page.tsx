"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Check,
  Sparkles,
  Search,
  Building2,
  MapPin,
  Laptop,
  Clock,
  GraduationCap,
  Bell,
  Send,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { createClient } from "@/lib/supabase/client";

// Available SP Cities
const CITIES = [
  { value: "all", label: "Todas as cidades" },
  { value: "São Paulo", label: "São Paulo" },
  { value: "Campinas", label: "Campinas" },
  { value: "Santos", label: "Santos" },
  { value: "São José dos Campos", label: "São José dos Campos" },
  { value: "Ribeirão Preto", label: "Ribeirão Preto" },
  { value: "Sorocaba", label: "Sorocaba" },
];

// Modality Options
const MODALITIES = [
  { id: "all", label: "Todas", desc: "Qualquer modalidade" },
  { id: "presencial", label: "Presencial", desc: "Aulas na unidade" },
  { id: "online", label: "Online / EaD", desc: "100% a distância" },
  { id: "hibrido", label: "Híbrido", desc: "Presencial + Online" },
] as const;

// Shifts
const SHIFTS = [
  { id: "qualquer", label: "Qualquer turno" },
  { id: "Manhã", label: "Manhã" },
  { id: "Tarde", label: "Tarde" },
  { id: "Noturno", label: "Noturno" },
  { id: "Integral", label: "Integral" },
] as const;

// Opportunity Types
const OPPORTUNITY_TYPES = [
  { id: "all", label: "Todas as Vagas", icon: "✨" },
  { id: "bolsa", label: "Bolsa de Estudo (PSG)", icon: "🎓" },
  { id: "gratuito", label: "Gratuito", icon: "🆓" },
  { id: "pago", label: "Curso Pago", icon: "💳" },
] as const;

export default function NewMonitorPage() {
  const router = useRouter();

  // Form State
  const [queryText, setQueryText] = useState("");
  const [allProviders, setAllProviders] = useState(true);
  const [senacSelected, setSenacSelected] = useState(true);

  const [state] = useState("SP");
  const [city, setCity] = useState("all");
  const [modality, setModality] = useState<"all" | "presencial" | "online" | "hibrido">("all");
  const [shift, setShift] = useState<string>("qualquer");
  const [opportunityType, setOpportunityType] = useState<"all" | "bolsa" | "gratuito" | "pago">("all");

  const [notifyTelegram, setNotifyTelegram] = useState(true);

  // Status State
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Provider Selection Logic
  const canSubmitProviders = allProviders || senacSelected;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const trimmedQuery = queryText.trim();
    if (!trimmedQuery) {
      setError("Por favor, informe o que você procura (ex: Python, Enfermagem...).");
      return;
    }

    if (!canSubmitProviders) {
      setError("Selecione ao menos um provedor de ensino para realizar as buscas.");
      return;
    }

    setSubmitting(true);

    try {
      const supabase = createClient();

      // 1. Obter usuário autenticado
      const {
        data: { user },
        error: userError,
      } = await supabase.auth.getUser();

      if (userError || !user) {
        router.push("/login");
        return;
      }

      // 2. Inserir em public.monitors
      const channels = ["dashboard"];
      if (notifyTelegram) {
        channels.push("telegram");
      }

      const { data: monitor, error: insertError } = await supabase
        .from("monitors")
        .insert({
          user_id: user.id,
          query_text: trimmedQuery,
          all_providers: allProviders,
          city: city === "all" ? null : city,
          state: state,
          modality: modality,
          opportunity_type: opportunityType,
          shift: shift === "qualquer" ? null : shift,
          active: true,
          notify_channels: channels,
        })
        .select("id")
        .single();

      if (insertError || !monitor) {
        console.error("Erro ao inserir monitor:", insertError);
        throw new Error(
          insertError?.message || "Não foi possível criar o monitoramento."
        );
      }

      // 3. Se !all_providers e Senac selecionado, associar em public.monitor_providers
      if (!allProviders && senacSelected) {
        const { data: prov, error: provError } = await supabase
          .from("providers")
          .select("id")
          .eq("slug", "senac_sp")
          .single();

        if (provError || !prov) {
          console.warn("Aviso: Provider senac_sp não encontrado:", provError);
        } else {
          const { error: mpError } = await supabase
            .from("monitor_providers")
            .insert({
              monitor_id: monitor.id,
              provider_id: prov.id,
            });

          if (mpError) {
            console.error("Erro ao vincular provedor ao monitor:", mpError);
          }
        }
      }

      // 4. Inserir em public.monitor_preferences
      const { error: prefError } = await supabase
        .from("monitor_preferences")
        .insert({
          monitor_id: monitor.id,
          notify_scholarship: true,
          notify_paid: true,
          notify_enrollment_open: true,
          notify_new_offer: true,
          notify_new_class: true,
          notify_date_changes: false,
        });

      if (prefError) {
        console.error("Erro ao salvar preferências:", prefError);
      }

      setSuccess(true);

      // 5. Redirecionar para a listagem
      setTimeout(() => {
        router.push("/dashboard/monitors");
      }, 1000);
    } catch (err: any) {
      setError(err?.message || "Ocorreu um erro ao salvar o monitoramento.");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-12">
      {/* Header & Back Link */}
      <div className="flex items-center gap-2">
        <Link href="/dashboard/monitors">
          <Button variant="ghost" size="sm" className="gap-1.5 text-slate-600 hover:text-slate-900">
            <ArrowLeft className="h-4 w-4" />
            Voltar para Meus Monitoramentos
          </Button>
        </Link>
      </div>

      <Card className="shadow-sm border-slate-200">
        <CardHeader className="space-y-1">
          <div className="flex items-center gap-2 text-blue-600 font-semibold text-xs uppercase tracking-wider">
            <Sparkles className="h-4 w-4" />
            Radar Multi-Plataforma
          </div>
          <CardTitle className="text-2xl font-bold text-slate-900">
            Criar Novo Monitoramento
          </CardTitle>
          <CardDescription className="text-sm text-slate-600">
            Configure seu radar de vagas e bolsas em instituições de ensino técnico e profissionalizante.
            O sistema busca periodicamente novas turmas e vagas remanescentes.
          </CardDescription>
        </CardHeader>

        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-8">
            {/* Feedback Alerts */}
            {error && (
              <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-800 flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-red-600 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold block">Erro ao salvar</span>
                  <span>{error}</span>
                </div>
              </div>
            )}

            {success && (
              <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-4 text-sm text-emerald-800 flex items-center gap-2.5">
                <Check className="h-5 w-5 text-emerald-600 shrink-0" />
                <span className="font-semibold">
                  Monitoramento criado com sucesso! Redirecionando para o dashboard...
                </span>
              </div>
            )}

            {/* 1. O que você procura? (Texto Livre) */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Search className="h-4 w-4 text-blue-600" />
                <Label htmlFor="query_text" className="text-base font-semibold text-slate-900">
                  O que você procura? <span className="text-red-500">*</span>
                </Label>
              </div>
              <p className="text-xs text-slate-500">
                Digite o nome do curso técnico, habilitação, área profissional ou tecnologia que deseja acompanhar.
              </p>
              <Input
                id="query_text"
                type="text"
                value={queryText}
                onChange={(e) => setQueryText(e.target.value)}
                placeholder="Ex: Python, Desenvolvimento de Sistemas, Enfermagem, Administração..."
                className="text-base py-5 placeholder:text-slate-400"
                required
                autoFocus
              />
            </div>

            {/* 2. Onde procurar? (Provedores Multi-Provider) */}
            <div className="space-y-3 pt-4 border-t border-slate-100">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-blue-600" />
                  <Label className="text-base font-semibold text-slate-900">
                    Onde procurar? (Instituições)
                  </Label>
                </div>
              </div>

              {/* Toggle Todas as Plataformas */}
              <div className="p-3.5 rounded-lg border border-slate-200 bg-slate-50 flex items-center justify-between">
                <div>
                  <div className="font-medium text-sm text-slate-900">
                    Todas as plataformas disponíveis
                  </div>
                  <div className="text-xs text-slate-500">
                    Monitora simultaneamente em todas as instituições ativas e adicionadas futuramente.
                  </div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={allProviders}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      setAllProviders(checked);
                      if (!checked) {
                        setSenacSelected(true);
                      }
                    }}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              {/* Provider List */}
              <div className="grid grid-cols-1 gap-2.5 pt-1">
                {/* Senac SP */}
                <label
                  className={`flex items-center justify-between p-3.5 rounded-lg border transition-all ${
                    allProviders
                      ? "bg-blue-50/40 border-blue-200 cursor-default"
                      : senacSelected
                      ? "border-blue-600 bg-blue-50/50 cursor-pointer"
                      : "border-slate-200 hover:bg-slate-50 cursor-pointer"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={allProviders ? true : senacSelected}
                      disabled={allProviders}
                      onChange={(e) => setSenacSelected(e.target.checked)}
                      className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 disabled:opacity-60"
                    />
                    <div>
                      <div className="font-semibold text-sm text-slate-900">
                        Senac São Paulo
                      </div>
                      <div className="text-xs text-slate-500">
                        Rede de unidades Senac SP, bolsas PSG e turmas regulares
                      </div>
                    </div>
                  </div>
                  <Badge variant="success" className="shrink-0 text-xs">
                    Disponível
                  </Badge>
                </label>

                {/* SENAI SP (Em breve) */}
                <div className="flex items-center justify-between p-3.5 rounded-lg border border-slate-200 bg-slate-50/70 opacity-60 cursor-not-allowed">
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      disabled
                      checked={false}
                      className="h-4 w-4 rounded border-slate-300 text-slate-400 cursor-not-allowed"
                    />
                    <div>
                      <div className="font-medium text-sm text-slate-700">
                        SENAI São Paulo
                      </div>
                      <div className="text-xs text-slate-500">
                        Escolas e centros de treinamento SENAI em São Paulo
                      </div>
                    </div>
                  </div>
                  <Badge variant="secondary" className="shrink-0 text-xs text-slate-500 border border-slate-200">
                    Em breve
                  </Badge>
                </div>

                {/* ETEC / CPS (Em breve) */}
                <div className="flex items-center justify-between p-3.5 rounded-lg border border-slate-200 bg-slate-50/70 opacity-60 cursor-not-allowed">
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      disabled
                      checked={false}
                      className="h-4 w-4 rounded border-slate-300 text-slate-400 cursor-not-allowed"
                    />
                    <div>
                      <div className="font-medium text-sm text-slate-700">
                        ETEC — Centro Paula Souza
                      </div>
                      <div className="text-xs text-slate-500">
                        Vestibulinhos e cursos modulares ETEC em SP
                      </div>
                    </div>
                  </div>
                  <Badge variant="secondary" className="shrink-0 text-xs text-slate-500 border border-slate-200">
                    Em breve
                  </Badge>
                </div>
              </div>
            </div>

            {/* 3. Localização (Estado & Cidade) */}
            <div className="space-y-3 pt-4 border-t border-slate-100">
              <div className="flex items-center gap-2">
                <MapPin className="h-4 w-4 text-blue-600" />
                <Label className="text-base font-semibold text-slate-900">
                  Localização
                </Label>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="state_select" className="text-xs text-slate-600">
                    Estado
                  </Label>
                  <select
                    id="state_select"
                    value={state}
                    disabled
                    className="w-full rounded-md border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700 cursor-not-allowed"
                  >
                    <option value="SP">São Paulo (SP)</option>
                  </select>
                </div>

                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="city_select" className="text-xs text-slate-600">
                    Cidade
                  </Label>
                  <select
                    id="city_select"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-600"
                  >
                    {CITIES.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* 4. Modalidade (Segmented Controls) */}
            <div className="space-y-3 pt-4 border-t border-slate-100">
              <div className="flex items-center gap-2">
                <Laptop className="h-4 w-4 text-blue-600" />
                <Label className="text-base font-semibold text-slate-900">
                  Modalidade
                </Label>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {MODALITIES.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setModality(m.id)}
                    className={`flex flex-col items-center justify-center p-3 rounded-lg border text-center transition-all ${
                      modality === m.id
                        ? "border-blue-600 bg-blue-50/70 text-blue-900 font-semibold ring-1 ring-blue-600"
                        : "border-slate-200 bg-white hover:bg-slate-50 text-slate-700"
                    }`}
                  >
                    <span className="text-sm">{m.label}</span>
                    <span className="text-[11px] text-slate-500 mt-0.5">{m.desc}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* 5. Turno (Segmented / Buttons) */}
            <div className="space-y-3 pt-4 border-t border-slate-100">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-blue-600" />
                <Label className="text-base font-semibold text-slate-900">
                  Turno / Período
                </Label>
              </div>

              <div className="flex flex-wrap gap-2">
                {SHIFTS.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setShift(s.id)}
                    className={`px-3.5 py-2 rounded-lg text-sm border font-medium transition-all ${
                      shift === s.id
                        ? "border-blue-600 bg-blue-600 text-white shadow-sm"
                        : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {/* 6. Tipo de Vaga / Oportunidade */}
            <div className="space-y-3 pt-4 border-t border-slate-100">
              <div className="flex items-center gap-2">
                <GraduationCap className="h-4 w-4 text-blue-600" />
                <Label className="text-base font-semibold text-slate-900">
                  Tipo de Vaga / Oportunidade
                </Label>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
                {OPPORTUNITY_TYPES.map((op) => (
                  <button
                    key={op.id}
                    type="button"
                    onClick={() => setOpportunityType(op.id)}
                    className={`flex items-center gap-2.5 p-3 rounded-lg border text-left transition-all ${
                      opportunityType === op.id
                        ? "border-blue-600 bg-blue-50/70 text-blue-900 font-semibold ring-1 ring-blue-600"
                        : "border-slate-200 bg-white hover:bg-slate-50 text-slate-700"
                    }`}
                  >
                    <span className="text-lg">{op.icon}</span>
                    <span className="text-xs sm:text-sm font-medium">{op.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* 7. Canais de Notificação */}
            <div className="space-y-3 pt-4 border-t border-slate-100">
              <div className="flex items-center gap-2">
                <Bell className="h-4 w-4 text-blue-600" />
                <Label className="text-base font-semibold text-slate-900">
                  Canais de Notificação
                </Label>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Dashboard (sempre ativo) */}
                <div className="flex items-center justify-between p-3.5 rounded-lg border border-slate-200 bg-slate-50">
                  <div className="flex items-center gap-3">
                    <Bell className="h-4 w-4 text-slate-500" />
                    <div>
                      <div className="font-semibold text-sm text-slate-900">
                        Painel Web (Dashboard)
                      </div>
                      <div className="text-xs text-slate-500">
                        Alertas registrados no histórico da sua conta
                      </div>
                    </div>
                  </div>
                  <Badge variant="secondary" className="text-xs text-slate-600 border border-slate-200">
                    Sempre ativo
                  </Badge>
                </div>

                {/* Telegram (ativo por padrão) */}
                <label
                  className={`flex items-center justify-between p-3.5 rounded-lg border cursor-pointer transition-all ${
                    notifyTelegram
                      ? "border-sky-500 bg-sky-50/50"
                      : "border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={notifyTelegram}
                      onChange={(e) => setNotifyTelegram(e.target.checked)}
                      className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                    />
                    <div>
                      <div className="font-semibold text-sm text-slate-900 flex items-center gap-1.5">
                        <Send className="h-3.5 w-3.5 text-sky-500" />
                        Telegram
                      </div>
                      <div className="text-xs text-slate-500">
                        Aviso instantâneo assim que uma vaga ou bolsa abrir
                      </div>
                    </div>
                  </div>
                  <Badge variant="default" className="bg-sky-500 text-white text-xs">
                    Recomendado
                  </Badge>
                </label>
              </div>
            </div>
          </CardContent>

          {/* Form Actions */}
          <div className="p-6 pt-4 flex flex-col-reverse sm:flex-row sm:justify-end gap-3 border-t border-slate-200 mt-6 bg-slate-50/50 rounded-b-xl">
            <Link href="/dashboard/monitors" className="w-full sm:w-auto">
              <Button type="button" variant="outline" className="w-full sm:w-auto">
                Cancelar
              </Button>
            </Link>
            <Button
              type="submit"
              disabled={submitting || success || !canSubmitProviders}
              className="w-full sm:w-auto gap-2 shadow-sm font-semibold"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Salvando Monitoramento...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  Criar Monitoramento
                </>
              )}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
