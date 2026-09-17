"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Send, CheckCircle2, Copy, ExternalLink, ShieldAlert, RefreshCw, KeyRound, AlertTriangle } from "lucide-react";

interface TelegramAccount {
  telegram_chat_id: number;
  telegram_username: string | null;
  first_name: string | null;
  is_active: boolean;
  linked_at: string;
}

export default function TelegramSettingsPage() {
  const [account, setAccount] = useState<TelegramAccount | null>(null);
  const [loading, setLoading] = useState(false);
  const [tokenData, setTokenData] = useState<{
    token: string;
    link_url: string;
    expires_at: string;
    bot_username: string;
  } | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerateToken() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/telegram/link-token", { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Falha ao gerar link");
      setTokenData(data);
    } catch (err: any) {
      setError(err.message || "Erro inesperado ao gerar token");
    } finally {
      setLoading(false);
    }
  }

  function handleCopy() {
    if (!tokenData) return;
    navigator.clipboard.writeText(tokenData.token);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  }

  function handleSimulateConnect() {
    // For local demo/preview without running telegram bot
    setAccount({
      telegram_chat_id: 987654321,
      telegram_username: "usuario_aluno",
      first_name: "Aluno",
      is_active: true,
      linked_at: new Date().toISOString(),
    });
    setTokenData(null);
  }

  function handleDisconnect() {
    setAccount(null);
    setTokenData(null);
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Integração com Telegram</h1>
        <p className="text-slate-500 mt-1">
          Receba notificações instantâneas no seu celular sempre que surgirem vagas ou bolsas nos cursos monitorados.
        </p>
      </div>

      {/* Status Card */}
      <Card className="border-slate-200">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <CardTitle className="text-lg flex items-center gap-2">
                <Send className="h-5 w-5 text-sky-500" />
                Status da Conexão
              </CardTitle>
              <CardDescription>
                Estado atual do vínculo com o bot oficial do CursoRadar
              </CardDescription>
            </div>
            {account ? (
              <Badge className="bg-emerald-100 text-emerald-800 border-emerald-200 text-sm px-3 py-1">
                <CheckCircle2 className="h-4 w-4 mr-1.5 inline" /> Conectado
              </Badge>
            ) : (
              <Badge variant="outline" className="text-slate-600 border-slate-300 text-sm px-3 py-1">
                Não Conectado
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {account ? (
            <div className="rounded-lg bg-slate-50 border border-slate-200 p-5 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Usuário Telegram</div>
                  <div className="text-sm font-semibold text-slate-900 mt-0.5">
                    @{account.telegram_username || "Privado"} ({account.first_name})
                  </div>
                </div>
                <div>
                  <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Chat ID</div>
                  <div className="text-sm font-semibold text-slate-900 mt-0.5 font-mono">
                    {account.telegram_chat_id}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Conectado em</div>
                  <div className="text-sm font-semibold text-slate-900 mt-0.5">
                    {new Date(account.linked_at).toLocaleDateString("pt-BR", {
                      day: "2-digit",
                      month: "short",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </div>
                </div>
              </div>

              <div className="pt-3 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
                <span>Alertas prioritários ativos para este canal.</span>
                <Button variant="outline" size="sm" onClick={handleDisconnect} className="text-rose-600 hover:text-rose-700 hover:bg-rose-50 border-rose-200">
                  Desconectar Telegram
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
                <div className="p-4 rounded-lg bg-sky-50/60 border border-sky-100">
                  <div className="w-8 h-8 rounded-full bg-sky-600 text-white font-bold flex items-center justify-center mx-auto mb-2 text-sm">1</div>
                  <h4 className="text-sm font-semibold text-slate-900">Gerar Token Seguro</h4>
                  <p className="text-xs text-slate-600 mt-1">Crie um token exclusivo de uso único com validade de 15 minutos.</p>
                </div>
                <div className="p-4 rounded-lg bg-sky-50/60 border border-sky-100">
                  <div className="w-8 h-8 rounded-full bg-sky-600 text-white font-bold flex items-center justify-center mx-auto mb-2 text-sm">2</div>
                  <h4 className="text-sm font-semibold text-slate-900">Abrir no Telegram</h4>
                  <p className="text-xs text-slate-600 mt-1">Clique no link direto ou procure pelo bot oficial no aplicativo.</p>
                </div>
                <div className="p-4 rounded-lg bg-sky-50/60 border border-sky-100">
                  <div className="w-8 h-8 rounded-full bg-sky-600 text-white font-bold flex items-center justify-center mx-auto mb-2 text-sm">3</div>
                  <h4 className="text-sm font-semibold text-slate-900">Ativação Automática</h4>
                  <p className="text-xs text-slate-600 mt-1">Envie o comando <code>/start</code> e sua conta será sincronizada.</p>
                </div>
              </div>

              {error && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg flex items-center gap-2 text-sm text-rose-700">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {tokenData ? (
                <div className="rounded-xl bg-slate-900 text-white p-6 space-y-5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs uppercase font-mono tracking-wider text-sky-400 font-semibold flex items-center gap-1.5">
                      <KeyRound className="h-4 w-4" /> Token de Vinculação Ativo
                    </span>
                    <span className="text-xs text-slate-400">
                      Válido por 15 minutos
                    </span>
                  </div>

                  <div className="bg-slate-800/80 rounded-lg p-4 border border-slate-700 flex items-center justify-between">
                    <span className="font-mono text-sm tracking-wider text-slate-200 break-all select-all">
                      {tokenData.token}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleCopy}
                      className="ml-3 shrink-0 bg-slate-700 text-slate-100 border-slate-600 hover:bg-slate-600"
                    >
                      <Copy className="h-3.5 w-3.5 mr-1" />
                      {copied ? "Copiado!" : "Copiar"}
                    </Button>
                  </div>

                  <div className="flex flex-col sm:flex-row gap-3 pt-2">
                    <a
                      href={tokenData.link_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-1"
                    >
                      <Button className="w-full bg-sky-500 hover:bg-sky-400 text-white font-medium">
                        <ExternalLink className="h-4 w-4 mr-2" />
                        Abrir Direto no Telegram
                      </Button>
                    </a>
                    <Button
                      variant="outline"
                      onClick={handleSimulateConnect}
                      className="bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700"
                    >
                      Simular Conexão (Demo)
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col sm:flex-row gap-3">
                  <Button
                    onClick={handleGenerateToken}
                    disabled={loading}
                    className="bg-sky-600 hover:bg-sky-700 text-white flex-1"
                  >
                    {loading ? (
                      <>
                        <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                        Gerando Link Seguro...
                      </>
                    ) : (
                      <>
                        <Send className="h-4 w-4 mr-2" />
                        Gerar Link de Conexão com Telegram
                      </>
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={handleSimulateConnect}
                    className="border-slate-300 text-slate-700 hover:bg-slate-100"
                  >
                    Simular Conectado
                  </Button>
                </div>
              )}
            </div>
          )}
        </CardContent>
        <CardFooter className="bg-slate-50/50 border-t border-slate-100 text-xs text-slate-500 flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-slate-400 shrink-0" />
          <span>Privacidade Garantida: Nunca solicitamos senhas. O bot apenas recebe comandos autorizados de alerta.</span>
        </CardFooter>
      </Card>
    </div>
  );
}
