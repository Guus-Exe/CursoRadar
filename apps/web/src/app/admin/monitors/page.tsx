"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Eye, Search, GraduationCap } from "lucide-react";

interface AdminMonitorItem {
  id: string;
  user_email: string;
  course_title: string;
  location_name: string;
  shifts: string[];
  bolsa_only: boolean;
  status: "ACTIVE" | "PAUSED";
  created_at: string;
}

const INITIAL_MONITORS: AdminMonitorItem[] = [
  {
    id: "mon-01",
    user_email: "carlos.silva@gmail.com",
    course_title: "Técnico em Desenvolvimento de Sistemas",
    location_name: "Lapa Faustolo",
    shifts: ["Manhã"],
    bolsa_only: true,
    status: "ACTIVE",
    created_at: "2026-09-12T10:00:00Z",
  },
  {
    id: "mon-02",
    user_email: "mariana.oliveira@outlook.com",
    course_title: "Técnico em Administração",
    location_name: "Lapa Tito",
    shifts: ["Manhã", "Noite"],
    bolsa_only: false,
    status: "ACTIVE",
    created_at: "2026-09-14T15:30:00Z",
  },
  {
    id: "mon-03",
    user_email: "pedro.santos@uol.com.br",
    course_title: "Técnico em Enfermagem",
    location_name: "Tiradentes",
    shifts: ["Tarde"],
    bolsa_only: true,
    status: "PAUSED",
    created_at: "2026-09-15T08:20:00Z",
  },
  {
    id: "mon-04",
    user_email: "juliana.costa@gmail.com",
    course_title: "Técnico em Desenvolvimento de Sistemas",
    location_name: "Lapa Faustolo",
    shifts: ["Noite"],
    bolsa_only: true,
    status: "ACTIVE",
    created_at: "2026-09-16T19:00:00Z",
  },
];

export default function AdminMonitorsPage() {
  const [monitors] = useState<AdminMonitorItem[]>(INITIAL_MONITORS);
  const [search, setSearch] = useState("");

  const filtered = monitors.filter(
    (m) =>
      m.course_title.toLowerCase().includes(search.toLowerCase()) ||
      m.user_email.toLowerCase().includes(search.toLowerCase()) ||
      m.location_name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <Eye className="h-7 w-7 text-purple-600" />
            Monitores Globais
          </h1>
          <p className="text-slate-500 mt-1">
            Lista de critérios conceituais cadastrados por todos os usuários do sistema.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Buscar por usuário, curso ou unidade..."
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
                <TableHead>Usuário</TableHead>
                <TableHead>Curso & Unidade</TableHead>
                <TableHead>Turnos Preferidos</TableHead>
                <TableHead>Filtro de Bolsa</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Criado Em</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((mon) => (
                <TableRow key={mon.id}>
                  <TableCell className="font-medium text-slate-900">
                    {mon.user_email}
                  </TableCell>
                  <TableCell>
                    <div className="font-medium text-slate-900">{mon.course_title}</div>
                    <div className="text-xs text-slate-500">{mon.location_name}</div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {mon.shifts.map((s) => (
                        <Badge key={s} variant="outline" className="text-[11px]">
                          {s}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell>
                    {mon.bolsa_only ? (
                      <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300">
                        Apenas Bolsa
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-slate-600">
                        Qualquer Vaga
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {mon.status === "ACTIVE" ? (
                      <Badge className="bg-emerald-100 text-emerald-800">ATIVO</Badge>
                    ) : (
                      <Badge variant="outline" className="text-slate-500">PAUSADO</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right text-xs text-slate-500">
                    {new Date(mon.created_at).toLocaleDateString("pt-BR")}
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
