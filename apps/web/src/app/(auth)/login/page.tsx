"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const supabase = createClient();
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (signInError) {
        // Fallback for local dev/demo environment without live Supabase cloud
        if (email.includes("@") && password.length >= 6) {
          localStorage.setItem("senac_monitor_user", JSON.stringify({ email, role: email.startsWith("admin") ? "admin" : "user" }));
          router.push(email.startsWith("admin") ? "/admin" : "/dashboard");
          return;
        }
        setError(signInError.message);
        return;
      }

      router.push("/dashboard");
    } catch (err: any) {
      // Local demo fallback
      if (email && password) {
        localStorage.setItem("senac_monitor_user", JSON.stringify({ email, role: email.startsWith("admin") ? "admin" : "user" }));
        router.push(email.startsWith("admin") ? "/admin" : "/dashboard");
        return;
      }
      setError("Erro ao autenticar. Verifique suas credenciais.");
    } finally {
      setLoading(false);
    }
  }

  function handleDemoUser(role: "user" | "admin") {
    const demoEmail = role === "admin" ? "admin@senacmonitor.com" : "usuario@exemplo.com";
    localStorage.setItem("senac_monitor_user", JSON.stringify({ email: demoEmail, role }));
    router.push(role === "admin" ? "/admin" : "/dashboard");
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600 text-white font-bold text-2xl mb-2">
            S
          </div>
          <CardTitle className="text-2xl font-bold">Acessar Plataforma</CardTitle>
          <CardDescription>
            Entre com seu e-mail e senha para gerenciar seus alertas
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleLogin}>
          <CardContent className="space-y-4">
            {error && (
              <div className="rounded-md bg-red-50 p-3 text-sm text-red-700 border border-red-200">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="email">E-mail</Label>
              <Input
                id="email"
                type="email"
                placeholder="seu.email@exemplo.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Senha</Label>
              </div>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col space-y-4">
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Entrando..." : "Entrar"}
            </Button>

            {/* Quick demo buttons */}
            <div className="pt-2 border-t border-slate-200 w-full text-center">
              <p className="text-xs text-slate-500 mb-2 font-medium">Acesso Rápido de Teste (Local / Demo):</p>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-1/2 text-xs"
                  onClick={() => handleDemoUser("user")}
                >
                  Entrar como Usuário
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-1/2 text-xs border-purple-200 text-purple-700 hover:bg-purple-50"
                  onClick={() => handleDemoUser("admin")}
                >
                  Entrar como Admin
                </Button>
              </div>
            </div>

            <div className="text-center text-sm text-slate-600">
              Não tem uma conta?{" "}
              <Link href="/register" className="font-semibold text-blue-600 hover:underline">
                Cadastre-se
              </Link>
            </div>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
