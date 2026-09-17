import Link from "next/link";
import { GraduationCap, Bell, ShieldCheck, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col bg-white">
      {/* Top Header */}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6">
          <div className="flex items-center space-x-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-600 text-white font-bold text-xl">
              C
            </div>
            <span className="text-xl font-bold tracking-tight text-slate-900">
              CursoRadar
            </span>
          </div>
          <div className="flex items-center space-x-3">
            <Link href="/login">
              <Button variant="ghost">Entrar</Button>
            </Link>
            <Link href="/register">
              <Button>Criar Conta</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1">
        <section className="mx-auto max-w-5xl px-4 py-16 sm:px-6 text-center lg:py-24">
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700 mb-6">
            <span className="flex h-2 w-2 rounded-full bg-blue-600 animate-pulse"></span>
            Plataforma Multiusuário Oficial
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight text-slate-900 sm:text-5xl lg:text-6xl">
            Nunca mais perca uma vaga ou bolsa no Senac SP.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-600">
            Cadastre seu interesse pelo curso, unidade e período. Nosso motor inteligente descobre turmas atuais e futuras, alertando você instantaneamente no Telegram.
          </p>
          <div className="mt-8 flex justify-center gap-4">
            <Link href="/register">
              <Button size="lg" className="gap-2">
                Começar a Monitorar Grátis <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="/login">
              <Button size="lg" variant="outline">
                Acessar Painel
              </Button>
            </Link>
          </div>

          {/* Value Props */}
          <div className="mt-16 grid grid-cols-1 gap-8 sm:grid-cols-3 text-left">
            <div className="rounded-xl border border-slate-200 p-6 bg-slate-50">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-600 mb-4">
                <Bell className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900">Alertas em Tempo Real</h3>
              <p className="mt-2 text-sm text-slate-600">
                Receba mensagens diretamente no seu Telegram no momento exato em que uma bolsa abre ou surge desistência.
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 p-6 bg-slate-50">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 text-emerald-600 mb-4">
                <GraduationCap className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900">Descoberta Inteligente</h3>
              <p className="mt-2 text-sm text-slate-600">
                Você monitora o curso e a unidade. Se a turma atual encerrar e o Senac lançar outra, o sistema continua monitorando automaticamente.
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 p-6 bg-slate-50">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100 text-purple-600 mb-4">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900">Seguro e Ético</h3>
              <p className="mt-2 text-sm text-slate-600">
                Sem automação invasiva ou compras automáticas. Apenas links oficiais diretos para você realizar sua inscrição com segurança.
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-slate-50 py-6 text-center text-xs text-slate-500">
        CursoRadar © 2026. Plataforma independente de acompanhamento de oportunidades públicas.
      </footer>
    </div>
  );
}
