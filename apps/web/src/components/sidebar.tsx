"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Eye,
  PlusCircle,
  Bell,
  Send,
  Settings,
  ShieldCheck,
  Users,
  Layers,
  Activity,
  AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface SidebarProps {
  isAdmin?: boolean;
  mobileOpen?: boolean;
  onClose?: () => void;
}

export function Sidebar({ isAdmin = false, mobileOpen = false, onClose }: SidebarProps) {
  const pathname = usePathname();

  const userNav = [
    { label: "Visão Geral", href: "/dashboard", icon: LayoutDashboard },
    { label: "Meus Monitoramentos", href: "/dashboard/monitors", icon: Eye },
    { label: "Novo Monitoramento", href: "/dashboard/monitors/new", icon: PlusCircle },
    { label: "Histórico de Alertas", href: "/dashboard/alerts", icon: Bell },
    { label: "Conectar Telegram", href: "/dashboard/settings/telegram", icon: Send },
  ];

  const adminNav = [
    { label: "Métricas Gerais", href: "/admin", icon: LayoutDashboard },
    { label: "Usuários", href: "/admin/users", icon: Users },
    { label: "Ofertas Conhecidas", href: "/admin/offers", icon: Layers },
    { label: "Todos Monitores", href: "/admin/monitors", icon: Eye },
    { label: "Alertas Emitidos", href: "/admin/alerts", icon: Bell },
    { label: "Saúde dos Workers", href: "/admin/workers", icon: Activity },
    { label: "Erros do Sistema", href: "/admin/errors", icon: AlertTriangle },
  ];

  const navItems = isAdmin ? adminNav : userNav;

  return (
    <>
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-slate-200 bg-white transition-transform duration-200 ease-in-out md:static md:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-16 items-center border-b border-slate-200 px-6">
          <Link href={isAdmin ? "/admin" : "/dashboard"} className="flex items-center gap-2 font-bold text-slate-900">
            <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg text-white font-bold", isAdmin ? "bg-purple-600" : "bg-blue-600")}>
              {isAdmin ? "A" : "S"}
            </div>
            <span>{isAdmin ? "Painel Admin" : "Senac Monitor"}</span>
          </Link>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-6">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider px-3 mb-2">
            {isAdmin ? "Administração" : "Menu Principal"}
          </div>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const active = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onClose}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                    active
                      ? isAdmin
                        ? "bg-purple-50 text-purple-700 font-semibold"
                        : "bg-blue-50 text-blue-700 font-semibold"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  )}
                >
                  <Icon className={cn("h-4 w-4", active ? (isAdmin ? "text-purple-700" : "text-blue-700") : "text-slate-400")} />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          {isAdmin ? (
            <div className="mt-8 border-t border-slate-200 pt-4">
              <Link
                href="/dashboard"
                className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"
              >
                Voltar para Visão do Usuário
              </Link>
            </div>
          ) : (
            <div className="mt-8 border-t border-slate-200 pt-4">
              <div className="rounded-lg bg-blue-50 p-3 text-xs text-blue-800">
                <p className="font-semibold mb-1">Dica:</p>
                Conecte seu Telegram em Configurações para receber avisos em tempo real.
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
