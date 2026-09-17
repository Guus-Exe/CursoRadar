"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Layers, Search, ExternalLink, RefreshCw } from "lucide-react";

interface TrackedOffer {
  id: string;
  external_id: string;
  institution_name: string;
  location_name: string;
  course_title: string;
  shift: string;
  vacancies_total: number;
  vacancies_bolsa: number;
  status: string;
  monitors_count: number;
  last_checked_at: string;
}

const INITIAL_OFFERS: TrackedOffer[] = [
  {
    id: "off-01",
    external_id: "109015",
    institution_name: "Senac SP",
    location_name: "Lapa Faustolo",
    course_title: "Técnico em Desenvolvimento de Sistemas",
    shift: "Manhã",
    vacancies_total: 4,
    vacancies_bolsa: 2,
    status: "DISPONIVEL",
    monitors_count: 14,
    last_checked_at: new Date(Date.now() - 45 * 1000).toISOString(),
  },
  {
    id: "off-02",
    external_id: "109016",
    institution_name: "Senac SP",
    location_name: "Lapa Faustolo",
    course_title: "Técnico em Desenvolvimento de Sistemas",
    shift: "Noite",
    vacancies_total: 0,
    vacancies_bolsa: 0,
    status: "ESGOTADO",
    monitors_count: 22,
    last_checked_at: new Date(Date.now() - 50 * 1000).toISOString(),
  },
  {
    id: "off-03",
    external_id: "112400",
    institution_name: "Senac SP",
    location_name: "Lapa Tito",
    course_title: "Técnico em Administração",
    shift: "Manhã",
    vacancies_total: 8,
    vacancies_bolsa: 5,
    status: "DISPONIVEL",
    monitors_count: 9,
    last_checked_at: new Date(Date.now() - 30 * 1000).toISOString(),
  },
  {
    id: "off-04",
    external_id: "113890",
    institution_name: "Senac SP",
    location_name: "Tiradentes",
    course_title: "Técnico em Enfermagem",
    shift: "Tarde",
    vacancies_total: 0,
    vacancies_bolsa: 0,
    status: "EM_BREVE",
    monitors_count: 18,
    last_checked_at: new Date(Date.now() - 20 * 1000).toISOString(),
  },
];

export default function AdminOffersPage() {
  const [offers] = useState<TrackedOffer[]>(INITIAL_OFFERS);
  const [search, setSearch] = useState("");

  const filtered = offers.filter(
    (o) =>
      o.course_title.toLowerCase().includes(search.toLowerCase()) ||
      o.location_name.toLowerCase().includes(search.toLowerCase()) ||
      o.external_id.includes(search)
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <Layers className="h-7 w-7 text-purple-600" />
            Ofertas Conhecidas & Rastreadas
          </h1>
          <p className="text-slate-500 mt-1">
            Catálogo de turmas rastreadas pelos workers em tempo real.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Buscar por curso, unidade ou ID de oferta..."
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
                <TableHead>Oferta / ID</TableHead>
                <TableHead>Instituição & Unidade</TableHead>
                <TableHead>Curso & Turno</TableHead>
                <TableHead>Vagas Pagas</TableHead>
                <TableHead>Vagas Bolsas</TableHead>
                <TableHead>Interessados</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Última Checagem</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((offer) => (
                <TableRow key={offer.id}>
                  <TableCell className="font-mono text-xs font-semibold text-slate-700">
                    #{offer.external_id}
                  </TableCell>
                  <TableCell>
                    <div className="font-medium text-slate-900">{offer.institution_name}</div>
                    <div className="text-xs text-slate-500">{offer.location_name}</div>
                  </TableCell>
                  <TableCell>
                    <div className="font-medium text-slate-900">{offer.course_title}</div>
                    <Badge variant="outline" className="text-[11px] mt-0.5">
                      {offer.shift}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-semibold text-slate-900">
                    {offer.vacancies_total}
                  </TableCell>
                  <TableCell>
                    <Badge
                      className={
                        offer.vacancies_bolsa > 0
                          ? "bg-emerald-100 text-emerald-800 border-emerald-300"
                          : "bg-slate-100 text-slate-500"
                      }
                    >
                      {offer.vacancies_bolsa}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-slate-600 font-medium">
                    {offer.monitors_count} usuários
                  </TableCell>
                  <TableCell>
                    {offer.status === "DISPONIVEL" ? (
                      <Badge className="bg-emerald-100 text-emerald-800">DISPONÍVEL</Badge>
                    ) : offer.status === "EM_BREVE" ? (
                      <Badge className="bg-amber-100 text-amber-800">EM BREVE</Badge>
                    ) : (
                      <Badge variant="outline" className="text-slate-500">ESGOTADO</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right text-xs text-slate-500 font-mono">
                    {new Date(offer.last_checked_at).toLocaleTimeString("pt-BR")}
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
