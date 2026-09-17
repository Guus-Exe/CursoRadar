"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Check, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";

// Progressive Catalog Data
const INSTITUTIONS = [
  { id: "senac-sp", name: "Senac — São Paulo" },
  { id: "senai-sp", name: "Senai — São Paulo (Em Breve)", disabled: true },
  { id: "etec", name: "Etec — Centro Paula Souza (Em Breve)", disabled: true },
];

const STATES = [{ id: "SP", name: "São Paulo (SP)" }];

const CITIES: Record<string, string[]> = {
  SP: ["São Paulo", "Campinas", "Santos", "São José dos Campos"],
};

const UNITS_BY_CITY: Record<string, string[]> = {
  "São Paulo": [
    "Senac Lapa Faustolo",
    "Senac Lapa Tito",
    "Senac Tiradentes",
    "Senac Santana",
    "Senac Tatuapé",
  ],
  Campinas: ["Senac Campinas"],
  Santos: ["Senac Santos"],
  "São José dos Campos": ["Senac São José dos Campos"],
};

const COURSES_BY_UNIT: Record<string, string[]> = {
  "Senac Lapa Faustolo": [
    "Técnico em Modelagem do Vestuário",
    "Técnico em Design de Interiores",
    "Técnico em Produção de Moda",
  ],
  "Senac Lapa Tito": [
    "Técnico em Informática",
    "Técnico em Desenvolvimento de Sistemas",
    "Técnico em Administração",
  ],
  "Senac Tiradentes": [
    "Técnico em Enfermagem",
    "Técnico em Farmácia",
    "Técnico em Radiologia",
  ],
};

const DEFAULT_COURSES = [
  "Técnico em Modelagem do Vestuário",
  "Técnico em Informática",
  "Técnico em Administração",
  "Técnico em Enfermagem",
  "Técnico em Design de Interiores",
];

const SHIFTS = ["Qualquer turno", "Noturno", "Manhã", "Tarde", "Integral"];

export default function NewMonitorPage() {
  const router = useRouter();

  // Cascading Selection State
  const [institution, setInstitution] = useState("senac-sp");
  const [state, setState] = useState("SP");
  const [city, setCity] = useState("São Paulo");
  const [unit, setUnit] = useState("Senac Lapa Faustolo");
  const [course, setCourse] = useState("Técnico em Modelagem do Vestuário");
  const [shift, setShift] = useState("Noturno");

  // Interests
  const [interestType, setInterestType] = useState<"both" | "scholarship" | "paid">("both");

  // Notifications toggles
  const [notifyEnrollmentOpen, setNotifyEnrollmentOpen] = useState(true);
  const [notifyScholarship, setNotifyScholarship] = useState(true);
  const [notifyNewOffer, setNotifyNewOffer] = useState(true);
  const [notifyNewClass, setNotifyNewClass] = useState(true);
  const [notifyDateChanges, setNotifyDateChanges] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  // Available options based on cascading selections
  const availableCities = CITIES[state] || ["São Paulo"];
  const availableUnits = UNITS_BY_CITY[city] || ["Senac Lapa Faustolo"];
  const availableCourses = COURSES_BY_UNIT[unit] || DEFAULT_COURSES;

  function handleCityChange(newCity: string) {
    setCity(newCity);
    const newUnits = UNITS_BY_CITY[newCity] || ["Senac Lapa Faustolo"];
    setUnit(newUnits[0]);
    const newCourses = COURSES_BY_UNIT[newUnits[0]] || DEFAULT_COURSES;
    setCourse(newCourses[0]);
  }

  function handleUnitChange(newUnit: string) {
    setUnit(newUnit);
    const newCourses = COURSES_BY_UNIT[newUnit] || DEFAULT_COURSES;
    setCourse(newCourses[0]);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);

    const newMonitor = {
      id: `mon-${Date.now()}`,
      course,
      institution: "Senac São Paulo",
      unit,
      shift,
      active: true,
      notifyScholarship: interestType === "both" || interestType === "scholarship",
      notifyPaid: interestType === "both" || interestType === "paid",
      notifyNewOffer: notifyNewOffer || notifyNewClass,
      lastChecked: "Agora",
      url: "https://www.sp.senac.br/senac-lapa-faustolo/cursos-tecnicos/curso-tecnico-em-modelagem-do-vestuario?bolsa=true&oferta=9900357333",
    };

    // Save locally
    const existingRaw = localStorage.getItem("senac_user_monitors");
    let existingList = [];
    if (existingRaw) {
      try {
        existingList = JSON.parse(existingRaw);
      } catch {}
    }
    existingList.push(newMonitor);
    localStorage.setItem("senac_user_monitors", JSON.stringify(existingList));

    setSubmitting(false);
    setSuccess(true);

    setTimeout(() => {
      router.push("/dashboard/monitors");
    }, 1200);
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-2">
        <Link href="/dashboard/monitors">
          <Button variant="ghost" size="sm" className="gap-1 text-slate-600">
            <ArrowLeft className="h-4 w-4" />
            Voltar
          </Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2 text-blue-600 font-semibold text-sm">
            <Sparkles className="h-4 w-4" />
            Assistente Inteligente
          </div>
          <CardTitle className="text-2xl font-bold text-slate-900">
            Criar Novo Monitoramento
          </CardTitle>
          <CardDescription>
            Defina o que você procura. Não se preocupe com códigos de turma ou links técnicos — nosso motor descobre automaticamente as turmas atuais e futuras.
          </CardDescription>
        </CardHeader>

        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-6">
            {success && (
              <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-4 text-emerald-800 flex items-center gap-2">
                <Check className="h-5 w-5 text-emerald-600" />
                <span className="font-semibold">Monitoramento criado com sucesso! Redirecionando...</span>
              </div>
            )}

            {/* 1. Instituição */}
            <div className="space-y-2">
              <Label htmlFor="institution">Instituição de Ensino</Label>
              <select
                id="institution"
                value={institution}
                onChange={(e) => setInstitution(e.target.value)}
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                {INSTITUTIONS.map((inst) => (
                  <option key={inst.id} value={inst.id} disabled={inst.disabled}>
                    {inst.name}
                  </option>
                ))}
              </select>
            </div>

            {/* 2. Estado e Cidade (Cascata) */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="state">Estado</Label>
                <select
                  id="state"
                  value={state}
                  onChange={(e) => setState(e.target.value)}
                  className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
                >
                  {STATES.map((st) => (
                    <option key={st.id} value={st.id}>
                      {st.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="city">Cidade</Label>
                <select
                  id="city"
                  value={city}
                  onChange={(e) => handleCityChange(e.target.value)}
                  className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
                >
                  {availableCities.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* 3. Unidade */}
            <div className="space-y-2">
              <Label htmlFor="unit">Unidade / Campus</Label>
              <select
                id="unit"
                value={unit}
                onChange={(e) => handleUnitChange(e.target.value)}
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                {availableUnits.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
            </div>

            {/* 4. Curso */}
            <div className="space-y-2">
              <Label htmlFor="course">Curso Desejado</Label>
              <select
                id="course"
                value={course}
                onChange={(e) => setCourse(e.target.value)}
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                {availableCourses.map((crs) => (
                  <option key={crs} value={crs}>
                    {crs}
                  </option>
                ))}
              </select>
            </div>

            {/* 5. Turno */}
            <div className="space-y-2">
              <Label htmlFor="shift">Período / Turno</Label>
              <select
                id="shift"
                value={shift}
                onChange={(e) => setShift(e.target.value)}
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                {SHIFTS.map((sh) => (
                  <option key={sh} value={sh}>
                    {sh}
                  </option>
                ))}
              </select>
            </div>

            {/* 6. Tipo de Interesse */}
            <div className="space-y-3 pt-2 border-t border-slate-200">
              <Label className="text-base font-semibold text-slate-900">
                Tenho interesse em:
              </Label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <label
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                    interestType === "scholarship"
                      ? "border-blue-600 bg-blue-50/50 text-blue-900 font-medium"
                      : "border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <input
                    type="radio"
                    name="interest"
                    checked={interestType === "scholarship"}
                    onChange={() => setInterestType("scholarship")}
                    className="h-4 w-4 text-blue-600"
                  />
                  <span>🎓 Apenas Bolsa (100% Gratuito PSG)</span>
                </label>

                <label
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                    interestType === "paid"
                      ? "border-blue-600 bg-blue-50/50 text-blue-900 font-medium"
                      : "border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <input
                    type="radio"
                    name="interest"
                    checked={interestType === "paid"}
                    onChange={() => setInterestType("paid")}
                    className="h-4 w-4 text-blue-600"
                  />
                  <span>💳 Apenas Curso Pago</span>
                </label>

                <label
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                    interestType === "both"
                      ? "border-blue-600 bg-blue-50/50 text-blue-900 font-medium"
                      : "border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <input
                    type="radio"
                    name="interest"
                    checked={interestType === "both"}
                    onChange={() => setInterestType("both")}
                    className="h-4 w-4 text-blue-600"
                  />
                  <span>✨ Ambos (O que abrir primeiro)</span>
                </label>
              </div>
            </div>

            {/* 7. Gatilhos de Notificação */}
            <div className="space-y-3 pt-2 border-t border-slate-200">
              <Label className="text-base font-semibold text-slate-900">
                Me avise quando:
              </Label>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={notifyEnrollmentOpen}
                    onChange={(e) => setNotifyEnrollmentOpen(e.target.checked)}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 h-4 w-4"
                  />
                  <span>Inscrições / matrículas regulares abrirem</span>
                </label>

                <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={notifyScholarship}
                    onChange={(e) => setNotifyScholarship(e.target.checked)}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 h-4 w-4"
                  />
                  <span>Bolsa de estudo (PSG) ou lista de espera abrir</span>
                </label>

                <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={notifyNewClass}
                    onChange={(e) => setNotifyNewClass(e.target.checked)}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 h-4 w-4"
                  />
                  <span>Aparecer nova turma para o mesmo curso na unidade</span>
                </label>

                <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={notifyNewOffer}
                    onChange={(e) => setNotifyNewOffer(e.target.checked)}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 h-4 w-4"
                  />
                  <span>O Senac atualizar o código da oferta para novas datas</span>
                </label>

                <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={notifyDateChanges}
                    onChange={(e) => setNotifyDateChanges(e.target.checked)}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 h-4 w-4"
                  />
                  <span>Datas importantes ou horário de início mudarem</span>
                </label>
              </div>
            </div>
          </CardContent>

          <div className="p-6 pt-0 flex justify-end gap-3 border-t border-slate-200 mt-6">
            <Link href="/dashboard/monitors">
              <Button type="button" variant="outline">
                Cancelar
              </Button>
            </Link>
            <Button type="submit" disabled={submitting || success}>
              {submitting ? "Salvando..." : "Criar Monitoramento"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
