import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CursoRadar — Plataforma de Vagas e Bolsas",
  description: "Monitoramento automatizado multiusuário de vagas, bolsas de estudo e novas turmas no Senac SP e instituições de ensino",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
