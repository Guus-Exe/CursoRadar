"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { LogOut, ShieldAlert, Bell, Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { createClient } from "@/lib/supabase/client";

export function Navbar({ onToggleSidebar }: { onToggleSidebar?: () => void }) {
  const [user, setUser] = useState<{ email?: string; name?: string | null; role?: string } | null>(null);

  useEffect(() => {
    const supabase = createClient();

    async function loadUser() {
      const {
        data: { user: authUser },
      } = await supabase.auth.getUser();

      if (!authUser) {
        setUser(null);
        return;
      }

      const { data: profile } = await supabase
        .from("profiles")
        .select("name, role")
        .eq("id", authUser.id)
        .maybeSingle();

      setUser({
        email: authUser.email,
        name: profile?.name || authUser.user_metadata?.name || null,
        role: profile?.role || "user",
      });
    }

    loadUser();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (_event, session) => {
      if (session?.user) {
        const { data: profile } = await supabase
          .from("profiles")
          .select("name, role")
          .eq("id", session.user.id)
          .maybeSingle();

        setUser({
          email: session.user.email,
          name: profile?.name || session.user.user_metadata?.name || null,
          role: profile?.role || "user",
        });
      } else {
        setUser(null);
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  async function handleLogout() {
    try {
      const supabase = createClient();
      await supabase.auth.signOut();
    } catch (err) {
      console.error("Erro ao encerrar sessão:", err);
    } finally {
      localStorage.removeItem("cursoradar_user");
      localStorage.removeItem("senac_monitor_user");
      window.location.href = "/login";
    }
  }

  return (
    <header className="sticky top-0 z-40 flex h-16 w-full items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-6">
      <div className="flex items-center gap-3">
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            className="md:hidden rounded-lg p-2 text-slate-600 hover:bg-slate-100"
          >
            <Menu className="h-5 w-5" />
          </button>
        )}
        <Link href="/dashboard" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 font-bold text-white">
            C
          </div>
          <span className="font-bold tracking-tight text-slate-900 hidden sm:inline">
            CursoRadar
          </span>
        </Link>
      </div>

      <div className="flex items-center gap-3">
        {user?.role === "admin" && (
          <Link href="/admin">
            <Button size="sm" variant="outline" className="gap-1.5 border-purple-200 text-purple-700 hover:bg-purple-50">
              <ShieldAlert className="h-4 w-4" />
              <span className="hidden sm:inline">Painel Admin</span>
            </Button>
          </Link>
        )}

        <Link href="/dashboard/alerts">
          <Button size="icon" variant="ghost" className="relative text-slate-600">
            <Bell className="h-5 w-5" />
            <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-blue-600" />
          </Button>
        </Link>

        <div className="flex items-center gap-2 border-l border-slate-200 pl-3">
          {user && (
            <div className="hidden sm:flex flex-col text-right">
              <span className="text-xs font-semibold text-slate-900">
                {user.name ? `${user.name} (${user.email})` : user.email}
              </span>
              <span className="text-[10px] text-slate-500 uppercase tracking-wider">{user.role || "user"}</span>
            </div>
          )}
          <Button size="icon" variant="ghost" onClick={handleLogout} title="Sair">
            <LogOut className="h-4 w-4 text-slate-500 hover:text-red-600" />
          </Button>
        </div>
      </div>
    </header>
  );
}
