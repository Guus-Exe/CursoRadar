"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Users, Search, ShieldCheck, Send, CheckCircle2, XCircle } from "lucide-react";

interface UserProfile {
  id: string;
  email: string;
  full_name: string | null;
  role: "admin" | "user";
  telegram_connected: boolean;
  monitors_count: number;
  created_at: string;
}

const INITIAL_USERS: UserProfile[] = [
  {
    id: "usr-01",
    email: "admin@cursoradar.local",
    full_name: "Administrador do Sistema",
    role: "admin",
    telegram_connected: true,
    monitors_count: 5,
    created_at: "2026-08-01T10:00:00Z",
  },
  {
    id: "usr-02",
    email: "carlos.silva@gmail.com",
    full_name: "Carlos Silva",
    role: "user",
    telegram_connected: true,
    monitors_count: 3,
    created_at: "2026-09-02T14:30:00Z",
  },
  {
    id: "usr-03",
    email: "mariana.oliveira@outlook.com",
    full_name: "Mariana Oliveira",
    role: "user",
    telegram_connected: false,
    monitors_count: 1,
    created_at: "2026-09-10T09:15:00Z",
  },
  {
    id: "usr-04",
    email: "pedro.santos@uol.com.br",
    full_name: "Pedro Santos",
    role: "user",
    telegram_connected: true,
    monitors_count: 4,
    created_at: "2026-09-12T18:40:00Z",
  },
  {
    id: "usr-05",
    email: "juliana.costa@gmail.com",
    full_name: "Juliana Costa",
    role: "user",
    telegram_connected: false,
    monitors_count: 2,
    created_at: "2026-09-15T11:20:00Z",
  },
];

export default function AdminUsersPage() {
  const [users, setUsers] = useState<UserProfile[]>(INITIAL_USERS);
  const [search, setSearch] = useState("");

  const filtered = users.filter(
    (u) =>
      u.email.toLowerCase().includes(search.toLowerCase()) ||
      (u.full_name && u.full_name.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <Users className="h-7 w-7 text-purple-600" />
            Gerenciamento de Usuários
          </h1>
          <p className="text-slate-500 mt-1">
            Visualização de contas cadastradas, níveis de acesso e integração Telegram.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Buscar por e-mail ou nome..."
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
                <TableHead>Perfil</TableHead>
                <TableHead>Telegram</TableHead>
                <TableHead>Monitores</TableHead>
                <TableHead>Cadastrado Em</TableHead>
                <TableHead className="text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((user) => (
                <TableRow key={user.id}>
                  <TableCell>
                    <div className="font-medium text-slate-900">{user.full_name || "Sem nome"}</div>
                    <div className="text-xs text-slate-500">{user.email}</div>
                  </TableCell>
                  <TableCell>
                    {user.role === "admin" ? (
                      <Badge className="bg-purple-100 text-purple-800 border-purple-200">
                        <ShieldCheck className="h-3 w-3 mr-1 inline" /> Admin
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-slate-600">
                        Usuário
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {user.telegram_connected ? (
                      <span className="flex items-center text-xs font-medium text-emerald-700">
                        <CheckCircle2 className="h-4 w-4 mr-1 text-emerald-600" /> Conectado
                      </span>
                    ) : (
                      <span className="flex items-center text-xs text-slate-400">
                        <XCircle className="h-4 w-4 mr-1 text-slate-300" /> Não vinculado
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="font-semibold text-slate-800">
                    {user.monitors_count}
                  </TableCell>
                  <TableCell className="text-xs text-slate-500">
                    {new Date(user.created_at).toLocaleDateString("pt-BR")}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="sm" className="text-xs text-purple-600 hover:text-purple-700">
                      Detalhes
                    </Button>
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
