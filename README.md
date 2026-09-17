# 🎓 Senac Monitor — Plataforma Multi-Usuário de Vagas e Bolsas

Plataforma completa e moderna para monitoramento contínuo e inteligente de **vagas regulares, bolsas de estudo (PSG 100% gratuitas), lista de espera e abertura de novas turmas** em instituições de ensino, com foco nativo no **Senac São Paulo**.

A plataforma evoluiu de um script single-user local para uma arquitetura distribuída completa:
- **Frontend Web:** Next.js 15 (App Router, Tailwind CSS, TypeScript, Lucide, shadcn/ui).
- **Backend & Banco de Dados:** PostgreSQL 15+ gerenciado via Supabase com Row Level Security (RLS).
- **Worker Desacoplado:** Motor em Python 3.12+ com APScheduler, HTTPX assíncrono e abstração `EducationProvider`.
- **Motor de Matching & Deduplicação:** $1$ requisição de rede para checar a oferta $\rightarrow$ $N$ usuários casados por critérios com idempotência via SHA256.
- **Telegram Multi-Usuário:** Vinculação segura de contas via tokens criptográficos de uso único (`/start <token>`), sem expor chat IDs no navegador.
- **Painel Administrativo:** Auditoria de usuários, catálogo de ofertas, telemetria de workers e logs de erros do sistema.

> ⚠️ **Aviso Ético:** A plataforma **não realiza matrículas automáticas**. Ela apenas detecta e notifica as oportunidades em tempo real com links oficiais diretos para que o usuário faça a inscrição com segurança.

---

## 🏛️ Arquitetura do Sistema

```
                        ┌──────────────────────────────────────────┐
                        │             Senac Monitor Web            │
                        │    (Next.js 15 / Tailwind / React 19)    │
                        └──────────────┬───────────────────────────┘
                                       │ Supabase Client & RLS
                                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          Supabase / PostgreSQL                           │
│  - profiles, telegram_accounts, telegram_link_tokens                     │
│  - institutions, locations, courses, offers                              │
│  - monitors, monitor_preferences, offer_checks, offer_changes, alerts    │
│  - worker_health, system_errors                                          │
└──────────────────────────────────────▲───────────────────────────────────┘
                                       │ Read tracked offers / Write alerts
                                       │ & worker health heartbeats
                        ┌──────────────┴───────────────────────────┐
                        │       Services: Python Worker Engine     │
                        │ (APScheduler, HTTPX, MatchingEngine)     │
                        └──────┬───────────────────────────┬───────┘
                               │ HTTP Checks               │ Telegram Bot API
                               ▼                           ▼
                 ┌──────────────────────────┐   ┌──────────────────────────┐
                 │    Portais de Ensino     │   │      Notificações &      │
                 │  - Senac SP Provider     │   │    Vinculação de Conta   │
                 │  - (Senai / Etec Futuro) │   │   via @BotFather Token   │
                 └──────────────────────────┘   └──────────────────────────┘
```

### Estrutura do Repositório

```
silly-volta/
├── apps/
│   └── web/                     # Aplicação Next.js 15 App Router
│       ├── src/app/             # Rotas: /, /login, /register, /dashboard, /admin
│       ├── src/components/      # Componentes UI (Navbar, Sidebar, Primitivas)
│       └── src/lib/supabase/    # Clients Supabase (browser, server, middleware)
├── services/
│   └── monitor/                 # Serviço contínuo em Python
│       ├── app/providers/       # Abstração EducationProvider & SenacSPProvider
│       ├── app/scrapers/        # Parsers HTML, APIs Senac e normalizador de turnos
│       ├── app/matching.py      # Motor de matching N-usuários e SHA256 fingerprints
│       ├── app/telegram_link.py # Gerenciador de tokens de vinculação do Telegram
│       ├── app/worker.py        # Orquestrador contínuo com telemetria e heartbeat
│       └── tests/               # 34 testes automatizados (100% de aprovação)
├── supabase/
│   ├── migrations/              # DDL versionado com RLS e triggers
│   └── seed.sql                 # Dados iniciais (Senac SP, unidades e cursos)
├── docker-compose.yml           # Orquestração do Web, Worker e Postgres
└── .env.example                 # Exemplo completo de variáveis de ambiente
```

---

## 🚀 Como Executar o Projeto

### Pré-requisitos
- **Node.js 20+** e **npm**
- **Python 3.12+** e gerenciador **uv**
- (Opcional) **Docker & Docker Compose**

---

### Opção 1: Executando Localmente (Desenvolvimento)

#### 1. Clonar e configurar o ambiente
```bash
cp .env.example .env
```

#### 2. Executar o Frontend (Next.js)
```bash
cd apps/web
npm install
npm run dev
```
Acesse a aplicação no navegador em `http://localhost:3000`.

#### 3. Executar o Worker de Monitoramento (Python)
Em outro terminal:
```bash
cd services/monitor
uv sync
uv run python -m app.main
```

---

### Opção 2: Executando com Docker Compose

Suba todo o stack (PostgreSQL, Worker e Web) com um único comando:
```bash
docker compose up --build
```
- **Web:** `http://localhost:3000`
- **Postgres:** `localhost:5432`

---

## 🧪 Testes Automatizados e Qualidade

O projeto possui **34 testes automatizados em Python** cobrindo todas as camadas críticas do sistema:
- **Resolução de conflito Turno/Horário:** Confirmação de que horários físicos (ex: 8h às 12h) prevalecem sobre códigos CMS errôneos.
- **Motor de Matching:** Simulação de 100 usuários monitorando a mesma oferta com 1 única requisição de rede e deduplicação de alertas via fingerprint.
- **Ciclo de Vida do Telegram Token:** Geração de 32-byte tokens criptográficos, uso único, expiração de 15 minutos e proteção contra replay.
- **Health Heartbeat:** Telemetria contínua dos workers e registro automático de incidentes na tabela `system_errors`.
- **Testes Históricos Legados:** 17 testes de regressão preservados e validados.

Para rodar todos os testes de backend:
```bash
uv run pytest services/monitor/tests -v
```

Para verificar o build e tipos do frontend Next.js:
```bash
cd apps/web
npm run build
```

---

## 📱 Fluxo de Vinculação com o Telegram

A integração multi-usuário com o Telegram dispensa qualquer digitação de IDs numéricos sensíveis:
1. O usuário entra no dashboard e acessa **Conectar Telegram** (`/dashboard/settings/telegram`).
2. Clica em **Gerar Link de Conexão com Telegram**.
3. O frontend chama a API `/api/telegram/link-token` que cria um token criptográfico temporário de 15 minutos.
4. O usuário clica em **Abrir Direto no Telegram**, sendo direcionado para `t.me/<BotUsername>?start=<TOKEN>`.
5. O bot consome o token, vincula a conta do Telegram ao `user_id` e envia uma confirmação no chat.

---

## 🛡️ Segurança & RLS (Row Level Security)

Todas as tabelas do Supabase possuem políticas ativas de RLS:
- **Usuários comuns:** Podem ler apenas seus próprios monitores, preferências, alertas e tokens vinculados.
- **Administradores (`role = 'admin'`):** Têm acesso de auditoria e visualização das métricas gerais, ofertas conhecidas, workers e logs de erro.
- **Workers e Serviços:** Comunicam-se utilizando `SUPABASE_SERVICE_ROLE_KEY` de uso estrito no backend, isolado de clientes públicos.
