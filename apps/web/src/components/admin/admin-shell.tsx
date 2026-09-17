"use client";

import { useState } from "react";
import { Sidebar } from "@/components/sidebar";
import { Navbar } from "@/components/navbar";
import { ShieldCheck } from "lucide-react";

interface AdminShellProps {
  children: React.ReactNode;
  user?: any;
  profile?: any;
}

export function AdminShell({
  children,
  user,
  profile,
}: AdminShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);

  const roleDisplay = profile?.role ? String(profile.role).toUpperCase() : "ADMIN";

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <Navbar onToggleSidebar={() => setMobileOpen(true)} />

      {/* Top Admin Banner */}
      <div className="bg-gradient-to-r from-purple-700 to-indigo-700 text-white px-6 py-2 text-xs flex items-center justify-between shadow-inner">
        <div className="flex items-center gap-2 font-medium">
          <ShieldCheck className="h-4 w-4" />
          <span>Área Restrita Administrativa: Acesso verificado ({roleDisplay})</span>
        </div>
        <span className="font-mono bg-purple-900/60 px-2 py-0.5 rounded text-[11px]">
          ROLE: ADMIN
        </span>
      </div>

      <div className="flex flex-1">
        <Sidebar
          isAdmin={true}
          mobileOpen={mobileOpen}
          onClose={() => setMobileOpen(false)}
        />

        <main className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
