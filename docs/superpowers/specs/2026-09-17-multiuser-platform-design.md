# Arquitetura e Especificação Técnica: Evolução Multi-Usuário do Senac Monitor

**Data:** 17 de Setembro de 2026  
**Status:** Aprovado  
**Tipo:** Arquitetural (Multi-User Platform Evolution)

---

## 1. Visão Geral do Produto

O **Senac Monitor** evolui de um monitor local/single-user com bot Telegram e SQLite para uma **plataforma web multiusuário completa** para acompanhamento de vagas, bolsas (PSG), lista de espera e abertura de novas turmas.

### Princípios Fundamentais:
1. **O usuário não monitora uma oferta específica:** O usuário cadastra seu interesse conceitual:
   $$\text{Instituição} \rightarrow \text{Unidade/Localização} \rightarrow \text{Curso} \rightarrow \text{Turno} \rightarrow \text{Preferências}$$
   O sistema é responsável por descobrir as ofertas presentes e futuras correspondentes sem exigir recadastro.
2. **Ofertas não pertencem ao usuário:** Uma oferta é consultada e mantida no banco **apenas uma vez** por ciclo de verificação, independentemente de quantos usuários a monitoram (1 oferta $\rightarrow$ 1 consulta HTTP $\rightarrow$ 1 detecção de evento $\rightarrow$ matching $\rightarrow$ $N$ notificações).
3. **Desacoplamento de Instituição:** A camada de coleta é baseada em `EducationProvider`, permitindo no futuro a integração transparente com Senai, Etec, Fatec e outras.
4. **Segurança e Isolamento Rigorosos:** Autenticação via Supabase Auth, Row Level Security (RLS) no PostgreSQL, tokens de vinculação do Telegram temporários e criptograficamente seguros (single-use), separação estrita de privilégios e nenhuma service role key exposta no frontend.

---

## 2. Estrutura do Monorepo

O repositório é reorganizado como monorepo preservando todo o histórico e utilitários existentes:

```
senac-monitor/
├── apps/
│   └── web/                     # Aplicação Next.js 14/15 App Router, TypeScript, Tailwind CSS, shadcn/ui
│       ├── src/
│       │   ├── app/             # Rotas: /login, /register, /dashboard/*, /admin/*, /api/*
│       │   ├── components/      # UI components (shadcn/ui, layout, tables, dialogs, forms)
│       │   ├── lib/             # Supabase clients (client, server, middleware), utils
│       │   └── types/           # Tipagens TypeScript compartilhadas
│       ├── public/
│       ├── package.json
│       └── tsconfig.json
│
├── services/
│   └── monitor/                 # Worker Python desacoplado (processo contínuo)
│       ├── app/
│       │   ├── config.py        # Configurações com Pydantic Settings
│       │   ├── models.py        # OfferState, StateDiff, DiscoveredOffer, MatchEvent
│       │   ├── database.py      # Camada de dados PostgreSQL / Supabase
│       │   ├── worker.py        # Orquestrador de verificação, descoberta e heartbeat
│       │   ├── matching.py      # Matching Engine entre OfferChanges e Monitors
│       │   ├── providers/       # Abstrações de Instituições
│       │   │   ├── base.py      # EducationProvider
│       │   │   └── senac.py     # SenacSPProvider
│       │   ├── scrapers/        # Parsers (Liferay XML, WSE-Bolsas, HTML fallback)
│       │   │   ├── offer_parser.py
│       │   │   └── senac_client.py
│       │   ├── notifications/   # Multi-user notification providers
│       │   │   ├── base.py
│       │   │   ├── telegram.py  # TelegramProvider multiusuário e bot de vinculação
│       │   │   └── whatsapp.py  # Stub preparado para WhatsApp
│       │   └── utils/
│       │       ├── diff.py      # Comparador de estados
│       │       └── logger.py
│       ├── tests/               # Testes automatizados (preservando baseline + novos)
│       └── pyproject.toml
│
├── supabase/
│   ├── migrations/              # Migrations SQL versionadas
│   │   └── 20260917000000_init_multiuser_schema.sql
│   └── seed.sql                 # Seed inicial (Senac SP, Lapa Faustolo, Modelagem, Admin)
│
├── docs/
│   ├── superpowers/specs/
│   └── superpowers/plans/
│
├── docker-compose.yml           # Orquestração local (Worker + PostgreSQL opcional)
├── Dockerfile                   # Build do worker de monitoramento
├── .env.example                 # Exemplo documentado de todas as variáveis
└── README.md                    # Documentação completa do projeto
```

---

## 3. Investigação e Resolução de Inconsistências Técnicas

### 3.1. Inconsistência de Turno (Turno Noturno vs Horário 8h às 12h)
- **Diagnóstico:**
  1. No código legado em `offer_parser.py`, o método `parse_html_offer` continha `turno = "Noturno"` como fallback fixo.
  2. A regex legada `\d{2}h\s*às\s*\d{2}h` exigia estritamente dois dígitos, falhando para capturar "8h" (1 dígito). Por não casar o padrão, o turno permanecia "Noturno" mesmo quando o texto era "8h às 12h".
  3. No método `SenacScraper.get_offer_state`, quando uma `target_offer_id` não era encontrada no XML retornado pelo endpoint Liferay, o código adotava silenciosamente o primeiro elemento `raw_offers[0]`. Se o primeiro elemento fosse uma turma da manhã (8h às 12h), ele lia os horários matutinos mas associava ao metadata esperado pelo usuário ou ao default.
  4. Em `normalize_shift`, quando `raw_shift` vinha preenchido com código como `"NO"`, a função retornava `"Noturno"` sem validar se `hours_text` contradizia frontalmente o período (ex.: horário das 8h às 12h).
- **Correção Definitiva:**
  1. Regex aprimorada em `normalize_shift`: `r'(?:das\s*|de\s*)?(\d{1,2})(?::\d{2})?h?'` aceitando 1 ou 2 dígitos e minutos opcionais.
  2. Validação cruzada: se o horário indicar categoricamente hora de início entre 5h e 11h59, classifica como `"Manhã"`; entre 12h e 17h59 como `"Tarde"`; entre 18h e 23h59 como `"Noturno"`. Em caso de divergência entre `raw_shift` e `hours_text`, o horário físico real da aula tem precedência e gera log de aviso sobre inconsistência do CMS da instituição.
  3. Remoção de default estático `"Noturno"` em `parse_html_offer`.
  4. Validação explícita de `target_offer_id` para evitar substituição cega por `raw_offers[0]`.
  5. Testes unitários dedicados em `tests/test_parser.py` e `tests/test_shift_normalization.py` cobrindo todos os formatos (1 e 2 dígitos, divergências e limites).

### 3.2. Credencial de Bolsas e Higienização de Segredos
- **Diagnóstico:** A constante `WSE_BOLSA_AUTH_TOKEN = "[REDACTED_SENAC_AUTH_TOKEN]"` estava hardcoded em `app/scrapers/senac.py`. Embora corresponda a um token público utilizado pela SPA do Senac no frontend, nenhum segredo/token deve ficar em código-fonte.
- **Correção:**
  1. O token é extraído exclusivamente de variável de ambiente `SENAC_BOLSA_AUTH` através de `Settings`.
  2. Implementado mecanismo resiliente em `senac_client.py`: caso a variável não esteja definida, tenta extrair o token dinamicamente dos scripts JavaScript públicos da página do curso (`main.*.js` do Senac).
  3. A credencial é mantida restrita ao ambiente do worker e **nunca** é exposta ao browser ou cliente Next.js.
  4. O histórico Git foi verificado e o arquivo `.env.example` foi devidamente atualizado.

---

## 4. Modelo de Dados Relacional (PostgreSQL / Supabase)

### 4.1. Tabelas Principais

```sql
-- Extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Perfis de Usuário vinculados ao Supabase Auth
CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    name TEXT,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Vínculos de Contas Telegram
CREATE TABLE public.telegram_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE UNIQUE,
    telegram_chat_id TEXT NOT NULL UNIQUE,
    telegram_username TEXT,
    telegram_first_name TEXT,
    verified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Tokens Temporários de Vinculação Telegram (Single-Use, Seguros)
CREATE TABLE public.telegram_link_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Catálogo de Instituições
CREATE TABLE public.institutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'SP',
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5. Unidades / Localidades
CREATE TABLE public.locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID NOT NULL REFERENCES public.institutions(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'SP',
    external_id TEXT, -- ex: categoryId Liferay 40814
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(institution_id, slug)
);

-- 6. Cursos
CREATE TABLE public.courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID NOT NULL REFERENCES public.institutions(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    category TEXT DEFAULT 'cursos-tecnicos',
    external_id TEXT, -- articleId / codigoFT
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(institution_id, slug)
);

-- 7. Ofertas Oficiais Coletadas (Não pertencem ao usuário)
CREATE TABLE public.offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID NOT NULL REFERENCES public.institutions(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES public.courses(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES public.locations(id) ON DELETE CASCADE,
    external_offer_id TEXT NOT NULL,
    shift TEXT NOT NULL,
    url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Indisponível',
    bolsa_disponivel BOOLEAN NOT NULL DEFAULT false,
    inscricao_disponivel BOOLEAN NOT NULL DEFAULT false,
    current_state_json JSONB,
    current_state_hash TEXT,
    first_detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    active BOOLEAN NOT NULL DEFAULT true,
    UNIQUE(institution_id, external_offer_id)
);

-- 8. Monitoramentos Cadastrados por Usuários
CREATE TABLE public.monitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    institution_id UUID NOT NULL REFERENCES public.institutions(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES public.locations(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES public.courses(id) ON DELETE CASCADE,
    shift TEXT, -- NULL significa qualquer turno
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 9. Preferências Específicas do Monitor
CREATE TABLE public.monitor_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    monitor_id UUID NOT NULL REFERENCES public.monitors(id) ON DELETE CASCADE UNIQUE,
    notify_scholarship BOOLEAN NOT NULL DEFAULT true,
    notify_paid BOOLEAN NOT NULL DEFAULT true,
    notify_enrollment_open BOOLEAN NOT NULL DEFAULT true,
    notify_new_offer BOOLEAN NOT NULL DEFAULT true,
    notify_new_class BOOLEAN NOT NULL DEFAULT true,
    notify_date_changes BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 10. Histórico de Verificações das Ofertas
CREATE TABLE public.offer_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    offer_id UUID NOT NULL REFERENCES public.offers(id) ON DELETE CASCADE,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_success BOOLEAN NOT NULL,
    status_code INTEGER NOT NULL DEFAULT 200,
    state_json JSONB,
    diff_json JSONB,
    error_message TEXT
);

-- 11. Eventos de Mudança Detectados em Ofertas
CREATE TABLE public.offer_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    offer_id UUID NOT NULL REFERENCES public.offers(id) ON DELETE CASCADE,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    change_type TEXT NOT NULL,
    previous_state_json JSONB,
    current_state_json JSONB,
    reasons TEXT[],
    is_actionable BOOLEAN NOT NULL DEFAULT false
);

-- 12. Alertas Enviados aos Usuários com Deduplicação Rigorosa
CREATE TABLE public.alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    monitor_id UUID NOT NULL REFERENCES public.monitors(id) ON DELETE CASCADE,
    offer_id UUID REFERENCES public.offers(id) ON DELETE SET NULL,
    change_id UUID REFERENCES public.offer_changes(id) ON DELETE SET NULL,
    alert_type TEXT NOT NULL,
    fingerprint TEXT NOT NULL UNIQUE,
    channel TEXT NOT NULL DEFAULT 'telegram',
    sent_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered BOOLEAN NOT NULL DEFAULT true,
    error_message TEXT,
    message_content TEXT NOT NULL
);

-- 13. Heartbeat e Saúde dos Workers
CREATE TABLE public.worker_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id TEXT NOT NULL,
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_cycle_at TIMESTAMPTZ,
    cycle_duration_seconds NUMERIC(8,2),
    offers_checked INTEGER DEFAULT 0,
    offers_succeeded INTEGER DEFAULT 0,
    offers_failed INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'healthy',
    metadata JSONB
);

-- 14. Log Centralizado de Erros do Sistema
CREATE TABLE public.system_errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,
    error_type TEXT NOT NULL,
    message TEXT NOT NULL,
    stack_trace TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.2. Políticas de Row Level Security (RLS)

```sql
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.telegram_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.telegram_link_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.institutions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.offers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.monitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.monitor_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.offer_checks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.offer_changes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.worker_health ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_errors ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid() AND role = 'admin' AND status = 'active'
  );
$$ LANGUAGE sql SECURITY DEFINER;

CREATE POLICY "Users can read own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = id OR is_admin());
CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id) WITH CHECK (auth.uid() = id AND role = 'user');
CREATE POLICY "Admins full access on profiles" ON public.profiles
    FOR ALL USING (is_admin());

CREATE POLICY "Users can view own telegram account" ON public.telegram_accounts
    FOR SELECT USING (auth.uid() = user_id OR is_admin());
CREATE POLICY "Users can delete own telegram account" ON public.telegram_accounts
    FOR DELETE USING (auth.uid() = user_id OR is_admin());

CREATE POLICY "Users manage own link tokens" ON public.telegram_link_tokens
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Public read institutions" ON public.institutions FOR SELECT TO authenticated USING (true);
CREATE POLICY "Public read locations" ON public.locations FOR SELECT TO authenticated USING (true);
CREATE POLICY "Public read courses" ON public.courses FOR SELECT TO authenticated USING (true);
CREATE POLICY "Admin write institutions" ON public.institutions FOR ALL USING (is_admin());
CREATE POLICY "Admin write locations" ON public.locations FOR ALL USING (is_admin());
CREATE POLICY "Admin write courses" ON public.courses FOR ALL USING (is_admin());

CREATE POLICY "Authenticated read offers" ON public.offers FOR SELECT TO authenticated USING (true);
CREATE POLICY "Admin manage offers" ON public.offers FOR ALL USING (is_admin());

CREATE POLICY "Users manage own monitors" ON public.monitors
    FOR ALL USING (auth.uid() = user_id OR is_admin());

CREATE POLICY "Users manage preferences of own monitors" ON public.monitor_preferences
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.monitors
            WHERE monitors.id = monitor_preferences.monitor_id
            AND (monitors.user_id = auth.uid() OR is_admin())
        )
    );

CREATE POLICY "Users read own alerts" ON public.alerts
    FOR SELECT USING (auth.uid() = user_id OR is_admin());

CREATE POLICY "Admin view checks" ON public.offer_checks FOR SELECT USING (is_admin());
CREATE POLICY "Admin view changes" ON public.offer_changes FOR SELECT USING (is_admin());
CREATE POLICY "Admin view worker health" ON public.worker_health FOR SELECT USING (is_admin());
CREATE POLICY "Admin view system errors" ON public.system_errors FOR SELECT USING (is_admin());
```

---

## 5. Fluxo de Conexão do Telegram (Multi-Usuário & Segurança)

1. Usuário no Dashboard Web clica em "Conectar Telegram".
2. Rota de API do Next.js `/api/telegram/link-token` gera um token criptográfico aleatório (32 bytes urlsafe), salva em `telegram_link_tokens` com expiração de 15 minutos e retorna `https://t.me/<BOT_USERNAME>?start=<TOKEN>`.
3. Usuário clica no link e envia `/start <TOKEN>` para o Bot do Telegram.
4. O Worker TelegramProvider valida o token contra a tabela `telegram_link_tokens`.
   - Se o token existir, não tiver expirado e não tiver sido usado (`used_at IS NULL`):
     - Insere ou atualiza `telegram_accounts` com `(user_id, telegram_chat_id, telegram_username, telegram_first_name, verified_at, active = true)`.
     - Marca o token como utilizado (`used_at = now()`).
     - Responde com mensagem de sucesso: "🎉 Telegram vinculado com sucesso ao Senac Monitor!".
   - Se o token for inválido, expirado ou já utilizado:
     - Responde: "⚠️ Link de vinculação expirado ou inválido. Por favor, acesse seu painel web e gere um novo link."
5. O painel do usuário reflete imediatamente o status "Conectado ✅ (@username)" com opção de desconectar.

---

## 6. Matching Engine e Deduplicação de Alertas

### 6.1. Ciclo de Matching
Quando o Worker detecta uma alteração em uma oferta (`OfferChange`):
1. Recupera todos os monitores ativos compatíveis com a oferta:
   - `monitor.active = true`
   - `monitor.institution_id = offer.institution_id`
   - `monitor.location_id = offer.location_id`
   - `monitor.course_id = offer.course_id`
   - `monitor.shift IS NULL OR LOWER(monitor.shift) = LOWER(offer.shift)`
2. Filtra pelas preferências do usuário (`monitor_preferences`):
   - Se vaga regular abriu: `notify_paid = true` ou `notify_enrollment_open = true`.
   - Se bolsa abriu: `notify_scholarship = true`.
   - Se nova oferta criada: `notify_new_offer = true`.
   - Se datas mudaram: `notify_date_changes = true`.
3. Garante que o usuário possui conta Telegram ativa vinculada (`telegram_accounts.active = true`).

### 6.2. Deduplicação por Fingerprint
Para cada tupla `(user_id, monitor_id, offer_id, change)`:
$$\text{fingerprint} = \text{SHA256}(\text{user\_id} + ":" + \text{monitor\_id} + ":" + \text{offer\_id} + ":" + \text{change\_type} + ":" + \text{state\_hash})$$
- O worker verifica se o `fingerprint` já existe na tabela `alerts`.
- Se existir, o envio é descartado imediatamente como idempotente.
- Se não existir, a mensagem formatada é enviada via Telegram API para o `telegram_chat_id` do usuário.
- Ao obter confirmação de entrega, o alerta é registrado na tabela `alerts` com a constraint `UNIQUE(fingerprint)`.

---

## 7. Frontend e Dashboard Web (Next.js, Tailwind CSS, shadcn/ui)

### 7.1. Rotas do Usuário
- `/login` e `/register`: Formulários modernos com validação via React Hook Form e Zod, autenticação Supabase.
- `/dashboard`: Painel com resumo dos monitores ativos, alertas recebidos nas últimas 24h, status da conexão com o Telegram e badge de saúde dos workers.
- `/dashboard/monitors`: Listagem dos monitores em formato de tabela/cards responsivos com badges de status, botões de pausar/retomar e exclusão com diálogo modal de confirmação.
- `/dashboard/monitors/new`: Assistente progressivo e reativo:
  1. Instituição (Senac SP inicial, preparado para outras)
  2. Estado / Cidade
  3. Unidade (ex: Senac Lapa Faustolo)
  4. Curso (ex: Técnico em Modelagem do Vestuário)
  5. Turno (Qualquer, Noturno, Manhã, Tarde, Integral)
  6. Preferências com checkboxes: Bolsas, Vagas pagas, Novas turmas, Mudança de datas.
- `/dashboard/alerts`: Feed completo e histórico de alertas recebidos pelo próprio usuário com filtro por data, tipo e link direto para a página oficial do curso.
- `/dashboard/settings/telegram`: Painel com QR Code, link clicável de conexão e status do vínculo.

### 7.2. Painel Administrativo (`/admin/*`)
- Proteção estrita server-side (`role == 'admin'` verificado no middleware e em server components).
- `/admin`: Métricas reais (total de usuários, usuários ativos, contas Telegram vinculadas, monitores ativos, ofertas rastreadas, taxa de sucesso de checks, alertas emitidos).
- `/admin/users`: Gerenciamento de usuários, alteração de status (ativo/inativo), visualização de monitores e desvinculação de Telegram.
- `/admin/offers`: Lista de todas as ofertas conhecidas no sistema, status atual, última verificação, link oficial e visualização do histórico de checks.
- `/admin/monitors`: Visão panorâmica de todos os monitoramentos de todos os usuários.
- `/admin/alerts`: Auditoria completa de alertas enviados em tempo real.
- `/admin/workers`: Monitor de saúde com heartbeat dos workers, tempo de ciclo e taxas de erro.
- `/admin/errors`: Log de erros operacionais e de scraping.

---

## 8. Estratégia de Testes

1. **Preservação dos 17 Testes Unitários/Integração Existentes:** Todos continuam passando em `services/monitor/tests/`.
2. **Novos Testes Automatizados no Worker:**
   - Teste de normalização e resolução de conflito de Turno (Manhã 8h às 12h vs Noturno).
   - Teste de geração, expiração e uso único de tokens de vinculação do Telegram.
   - Teste de proteção contra reutilização ou falsificação de Telegram Chat ID.
   - Teste de matching com 100 usuários monitorando a mesma oportunidade: 1 consulta HTTP mockada $\rightarrow$ 100 matches calculados $\rightarrow$ 100 alertas gerados sem duplicações.
   - Teste de deduplicação idempotente com fingerprints.
   - Teste de heartbeat e registro de saúde do worker.
3. **Testes do Frontend e E2E:**
   - Lint, TypeCheck (`tsc --noEmit`) e Build (`npm run build`).
   - Validação com `agent-browser` (Chrome DevTools):
     - Fluxo de login e autenticação.
     - Criação, edição, pausa e exclusão de monitor.
     - Acesso à página de alertas e configurações de Telegram.
     - Responsividade comprovada em 375px (mobile), 768px (tablet) e 1440px (desktop).
