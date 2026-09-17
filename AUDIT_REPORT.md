# 🔍 AUDITORIA TÉCNICA DE SEGURANÇA E INTEGRIDADE — CURSORADAR

**Data e Hora da Auditoria:** 17 de Setembro de 2026 — 13:35 (BRT) / 16:35 (UTC)  
**Projeto Auditado:** **CursoRadar** (Autorizado)  
**Projeto de Referência de Isolamento:** **Trenex** (Preservado / Intacto)  
**Modo de Operação:** **READ ONLY / SOMENTE LEITURA** (Nenhuma mutação ou rollback realizado)  
**Skills Técnicas Consultadas:**
- `supabase` (`.agents/skills/supabase/SKILL.md`)
- `supabase-postgres-best-practices` (`.agents/skills/supabase-postgres-best-practices/SKILL.md`)
- `deploy-to-vercel` (`.agents/skills/deploy-to-vercel/SKILL.md`)

---

## 1. RESUMO EXECUTIVO

O projeto **CursoRadar** tem como objetivo evoluir o monitorador de bolsas e vagas de cursos técnicos do Senac SP de um protótipo local em linha de comando para uma plataforma multiusuário moderna e distribuída, integrando uma aplicação web Next.js 15, banco de dados relacional PostgreSQL hospedado no Supabase com Row Level Security (RLS), motor de matching desacoplado e worker contínuo de varredura.

### Diagnóstico Geral
1. **Isolamento de Projetos (100% Confirmado):** O projeto `Trenex` (`exyelntdpfbjyxkryrxj`) encontra-se no status `INACTIVE` e **não sofreu absolutamente nenhuma alteração, migração, inserção ou contaminação** decorrente do desenvolvimento do CursoRadar. Todas as operações de banco foram direcionadas com sucesso e com exclusividade para o projeto Supabase `CursoRadar` (`rbqqilyupzyibacytdwp`).
2. **Banco de Dados & RLS (Parcialmente Saudável com Vulnerabilidades):** Todas as 14 tabelas públicas planejadas foram criadas no Supabase com RLS ativo e os dados de seed do Senac SP foram inseridos. No entanto, a auditoria automatizada através de `supabase db advisors` e inspeção manual das migrations revelou uma **vulnerabilidade crítica (P0)** de escalada de privilégios (`handle_new_user` permite autoatribuição de `role = 'admin'`), além de 8 alertas de performance de RLS (`auth.uid()` avaliado por linha em vez de `(select auth.uid())`) e 7 chaves estrangeiras sem índices de cobertura.
3. **Frontend Next.js (Mock / Parcial):** O frontend Next.js 15 possui interface visual polida, compilando estática e dinamicamente (19 rotas com zero erros de compilação em `npm run build`), mas a maioria das páginas de dashboard e administração opera com **dados mockados e simulação em `localStorage`**, sem persistência real no Supabase.
4. **Área Administrativa (P1 - Falha de Autorização):** A rota `/admin` não valida a role do usuário no middleware nem no layout React, permitindo que usuários comuns autenticados visualizem a interface administrativa.
5. **Worker Python (Parcial / Desconectado do Supabase):** O código do worker em `services/monitor` possui boa cobertura de testes unitários (34/34 testes passando), mas a camada de persistência ainda utiliza SQLite local (`monitor.db`) e estruturas em memória (`dict`), não estando ainda conectada ao PostgreSQL do Supabase.
6. **Higiene de Repositório & Git (P1):** O arquivo `.gitignore` omite regras essenciais para o ecossistema Next.js, deixando `apps/web/.env.local`, `apps/web/node_modules/` e `apps/web/.next/` vulneráveis a commit acidental. Existem pastas legadas duplicadas (`app/` e `tests/`) na raiz do repositório.

---

## 2. VALIDAÇÃO DE ISOLAMENTO DE AMBIENTES (REGRA CRÍTICA)

Antes do início de qualquer inspeção técnica, os identificadores de ambiente foram validados:

| Parâmetro | Valor Identificado | Validação |
| :--- | :--- | :---: |
| **Diretório Local** | `C:\Users\gusta\Documents\antigravity\silly-volta` | OK |
| **Nome do Projeto** | `CursoRadar` (senac-monitor) | OK |
| **Branch Git** | `master` (sem remote vinculado) | OK |
| **Supabase Project Ref** | `rbqqilyupzyibacytdwp` | OK (CursoRadar) |
| **Supabase URL** | `https://rbqqilyupzyibacytdwp.supabase.co` | OK |
| **Supabase Status** | `ACTIVE_HEALTHY` | OK |
| **Project Ref Trenex** | `exyelntdpfbjyxkryrxj` | **INACTIVE / Zero mutações** |
| **Busca de Referências a Trenex** | 0 arquivos locais contendo 'trenex' ou 'exyelntdpfbjyxkryrxj' | OK |

---

## 3. AUDITORIA DETALHADA DO SUPABASE

### 3.1. Estrutura do Banco e Integridade Referencial
O banco do CursoRadar (`rbqqilyupzyibacytdwp`) contém 14 tabelas públicas:
1. `public.profiles`
2. `public.telegram_accounts`
3. `public.telegram_link_tokens`
4. `public.institutions`
5. `public.locations`
6. `public.courses`
7. `public.offers`
8. `public.monitors`
9. `public.monitor_preferences`
10. `public.offer_checks`
11. `public.offer_changes`
12. `public.alerts`
13. `public.worker_health`
14. `public.system_errors`

* **Chaves Primárias:** Todas as tabelas possuem chave primária UUID gerada com `gen_random_uuid()` (com exceção de `profiles.id` que é UUID referenciando `auth.users(id) ON DELETE CASCADE`).
* **Defaults e Timestamps:** Colunas de timestamp possuem `DEFAULT NOW()`, e tabelas mutáveis possuem trigger acionando `set_current_timestamp_updated_at()`.

### 3.2. Comparação com a Skill `supabase-postgres-best-practices`
A execução do linter nativo do Supabase (`supabase db advisors` via MCP `get_advisors`) revelou os seguintes problemas:

#### A. Índices de Chaves Estrangeiras Faltantes (`schema-foreign-key-indexes.md`)
Postgres não indexa colunas de chave estrangeira automaticamente. Sem índices, operações de `JOIN` e exclusões em cascata (`ON DELETE CASCADE`) geram `Seq Scan` e locks de tabela:
1. `public.alerts (change_id)` — sem índice.
2. `public.alerts (monitor_id)` — sem índice.
3. `public.alerts (offer_id)` — sem índice.
4. `public.monitors (course_id)` — sem índice individual (existe apenas em índice composto).
5. `public.monitors (location_id)` — sem índice individual.
6. `public.offers (course_id)` — sem índice individual.
7. `public.offers (location_id)` — sem índice individual.

#### B. Desempenho de Políticas RLS (`security-rls-performance.md`)
Conforme o guia de melhores práticas do Supabase, invocar funções dinâmicas como `auth.uid()` diretamente na cláusula `USING` faz com que a função seja executada para **cada linha avaliada na query** ($O(N)$). O padrão recomendado é encapsular com `(SELECT auth.uid())` ($O(1)$, com cache de plano):
- `public.profiles` (`Users can read own profile` e `Users can update own profile`)
- `public.telegram_accounts` (`Users can view own telegram account` e `Users can delete own telegram account`)
- `public.telegram_link_tokens` (`Users manage own link tokens`)
- `public.monitors` (`Users manage own monitors`)
- `public.monitor_preferences` (`Users manage preferences of own monitors`)
- `public.alerts` (`Users read own alerts`)

#### C. Políticas Permissivas Excessivas (`references/_sections.md`)
Identificadas 45 ocorrências de `multiple_permissive_policies`. Exemplo: na tabela `alerts`, existem duas políticas `FOR SELECT`: uma de admin (`is_admin()`) e uma de usuário (`auth.uid() = user_id`). Ambas estão sem cláusula de role (`TO authenticated`), o que força o Postgres a combinar ambas com `OR` para todos os papéis (inclusive `anon`), degradando a performance.

### 3.3. Auditoria de Segurança RLS e Funções
Executamos inspeção minuciosa de segurança:

#### [P0 — CRÍTICO] Escalada de Privilégios no Cadastro de Usuários
- **Local:** `supabase/migrations/20260917000000_init_multiuser_schema.sql:40-54`
- **Código Vulnerável:**
  ```sql
  CREATE OR REPLACE FUNCTION public.handle_new_user()
  RETURNS TRIGGER AS $$
  BEGIN
    INSERT INTO public.profiles (id, email, name, role, status)
    VALUES (
      NEW.id,
      NEW.email,
      COALESCE(NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1)),
      COALESCE(NEW.raw_user_meta_data->>'role', 'user'), -- VULNERABILIDADE!
      'active'
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
  END;
  $$ LANGUAGE plpgsql SECURITY DEFINER;
  ```
- **Violação da Skill `supabase`:**
  > *"Never use user_metadata claims in JWT-based authorization decisions. In Supabase, raw_user_meta_data is user-editable and can appear in auth.jwt(), so it is unsafe for RLS policies or any other authorization logic."*
- **Impacto:** Um usuário mal-intencionado ao criar conta via `supabase.auth.signUp({ email, password, options: { data: { role: 'admin' } } })` terá a coluna `role` gravada como `'admin'`. Como a função `is_admin()` verifica `profiles.role = 'admin'`, o invasor ganha privilégios de administrador de todo o banco e das rotas do sistema.

#### [P1 — ALTO] Funções `SECURITY DEFINER` Expostas na API REST Pública
- **Local:** `public.handle_new_user()` e `public.is_admin()`
- **Diagnóstico:** O PostgreSQL por padrão concede permissão `EXECUTE` a `PUBLIC`. Por estarem no schema `public` com `SECURITY DEFINER`, endpoints automáticos `/rest/v1/rpc/handle_new_user` e `/rest/v1/rpc/is_admin` ficam acessíveis tanto para `anon` quanto para `authenticated`.
- **Correção Necessária:** Executar `REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM PUBLIC, anon, authenticated;`.

#### [P2 — MÉDIO] `search_path` Mutável em Funções de Banco
- **Local:** `public.is_admin`, `public.set_current_timestamp_updated_at`, `public.handle_new_user`.
- **Diagnóstico:** As funções não fixam `SET search_path = ''` ou `SET search_path = public`, abrindo margem para search path hijacking por papéis privilegiados.

### 3.4. Service Role Key
- A chave `SUPABASE_SERVICE_ROLE_KEY` foi auditada. Ela **não** está exposta em bundles de frontend, **não** foi commitada no Git e **não** está presente em `apps/web/.env.local`.

### 3.5. Storage & Edge Functions
- `storage.buckets`: 0 buckets configurados.
- `edge_functions`: 0 funções implantadas.

---

## 4. AUDITORIA DO FRONTEND & BACKEND

### 4.1. Frontend Next.js 15 (`apps/web`)
* **Estrutura:** Next.js 15.1.7 (App Router), React 19, Tailwind CSS 3.4, Lucide React, componentes shadcn/ui.
* **Compilação:** O build de produção (`npm run build`) concluiu com sucesso para todas as 19 rotas. O tipo TypeScript (`tsc --noEmit`) passou com zero erros.
* **Diagnóstico de Implementação Real vs Mock:**
  - **Autenticação:** As telas `login/page.tsx` e `register/page.tsx` utilizam `createClient()` de `@/lib/supabase/client`, mas possuem fallback silencioso para `localStorage` caso ocorra qualquer erro de conexão com a nuvem.
  - **Dashboard de Aluno (`/dashboard/*`):** As páginas de listagem (`monitors/page.tsx`) e criação de monitoramento (`monitors/new/page.tsx`) **não realizam chamadas à API do Supabase**. Elas salvam os dados em `localStorage.getItem("senac_user_monitors")` e utilizam arrays estáticos para unidades e cursos (`INSTITUTIONS`, `UNITS_BY_CITY`, `COURSES_BY_UNIT`).
  - **Área Administrativa (`/admin/*`):** Todos os números, telemetrias e listas de usuários são mocks hardcoded (`INITIAL_USERS`, métricas fixas).
  - **Rota de Token do Telegram (`api/telegram/link-token`):**
    - [P2] Incompatibilidade de Schema: A rota tenta inserir `{ used: false }` na tabela `telegram_link_tokens`, mas a coluna no banco chama-se `used_at` (do tipo `TIMESTAMPTZ`).
    - [P2] Fallback Inseguro: Caso o usuário não esteja logado, a rota utiliza um UUID fictício `"00000000-0000-0000-0000-000000000001"`, violando a integridade referencial.
* **Controle de Acesso em `/admin`:**
  - [P1] O middleware `apps/web/src/lib/supabase/middleware.ts` verifica apenas se o usuário está logado (`if (!user && isProtectedRoute)`), redirecionando para login. Qualquer usuário regular cadastrado consegue acessar diretamente rotas `/admin/*`. O `AdminLayout` é um componente `"use client"` que não valida a role.

### 4.2. Backend / Worker de Monitoramento (`services/monitor`)
* **Stack:** Python 3.12+, Pydantic Settings, HTTPX, BeautifulSoup4, SQLAlchemy, APScheduler, python-telegram-bot.
* **Testes:** 34 testes unitários passando em 5.94s (`pytest services/monitor/tests -v`).
* **Diagnóstico de Conexão com o Banco:**
  - O arquivo `services/monitor/app/database.py` implementa persistência com SQLite local (`senac_monitor.db`). Não há suporte a PostgreSQL implementado nele (ausência de driver `asyncpg`/`psycopg2` em `pyproject.toml`).
  - O arquivo `services/monitor/app/worker.py` mantém a lista de monitores em memória (`self.active_monitors: List[UserMonitor] = []`), não consultando as tabelas `public.monitors` e `public.offers` do Supabase.
  - O arquivo `services/monitor/app/telegram_link.py` gerencia os tokens de vinculação em um dicionário em memória (`dict`), sem consultar `public.telegram_link_tokens`.
* **Credenciais e Segredos:**
  - [P1] O arquivo `services/monitor/app/config.py` possui um valor default estático hardcoded: `senac_bolsa_auth: str = Field(default="[REDACTED_AUTH_TOKEN]", ...)`. O token deve ser lido estritamente via variável de ambiente sem fallback hardcoded no repositório.

---

## 5. AUDITORIA DE VARIÁVEIS DE AMBIENTE

| Variável | Escopo / Classificação | Onde Está Declarada | Status / Observação |
| :--- | :--- | :--- | :--- |
| `NEXT_PUBLIC_SUPABASE_URL` | Pública (Browser) | `apps/web/.env.local` | OK (`https://rbqqilyupzyibacytdwp.supabase.co`) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Pública (Browser) | `apps/web/.env.local` | OK (Token JWT com payload ref `rbqqilyupzyibacytdwp`) |
| `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME` | Pública (Browser) | `apps/web/.env.local` | OK (`SenacMonitorAlertsBot`) |
| `SUPABASE_SERVICE_ROLE_KEY` | Secret (Server-side) | `.env.example` (mock) | OK (Nunca incluída no frontend) |
| `DATABASE_URL` | Secret (Worker) | `.env.example` (mock) | Ausente no ambiente do worker |
| `TELEGRAM_BOT_TOKEN` | Secret (Worker) | `.env.example` (mock) | Ausente no ambiente do worker |
| `SENAC_BOLSA_AUTH` | Secret (Worker) | `config.py` (hardcoded default) | **P1: Token default no código-fonte** |

---

## 6. AUDITORIA DE GIT & HIGIENE DO REPOSITÓRIO

* **Status Git:** Branch `master`, 1 commit inicial vazio (`dbdd8e7 Initial commit`).
* **Remote Git:** Nenhum remote configurado (`git remote -v` vazio).
* **[P1 — ALTO] Vulnerabilidade em `.gitignore`:**
  - O arquivo `.gitignore` na raiz contém regras para Python, mas **não ignora** os artefatos de build e segredos do Next.js.
  - O arquivo `apps/web/.env.local` está desprotegido e aparece como untracked. Um `git add .` cometeria este arquivo.
  - As pastas `apps/web/node_modules/` e `apps/web/.next/` não possuem regras de exclusão no root `.gitignore` nem existe um `.gitignore` dentro de `apps/web`.
* **[P3 — BAIXO] Código Morto / Duplicado:**
  - Pastas `app/` e `tests/` na raiz do projeto são duplicatas legadas anteriores à refatoração para monorepo (`services/monitor/app` e `services/monitor/tests`).

---

## 7. AUDITORIA DE DEPLOY NA VERCEL

Em conformidade com a skill `deploy-to-vercel`:
1. **Status de Vinculação:** O projeto **não está vinculado** à Vercel (`.vercel/project.json` e `.vercel/repo.json` inexistentes).
2. **Autenticação Vercel CLI:** `npx vercel whoami` reportou `loggedIn: false`. Nenhuma conta conectada localmente.
3. **Monorepo / Root Directory:** Como o Next.js está localizado em `apps/web/`, o deploy na Vercel falhará se não for configurado o **Root Directory: `apps/web`** nas configurações de projeto da Vercel ou via `vercel.json`.
4. **Variáveis de Ambiente para Deploy:** Devem ser inseridas no painel da Vercel (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME`).
5. **Build Command & Output:** `npm run build` e `.next` funcionam perfeitamente para deploy.

---

## 8. MATRIZ DE COMPARATIVO: PLANEJADO VS. IMPLEMENTADO

| Item Planejado | Planejado | Implementado | Funcionando | Observação |
| :--- | :---: | :---: | :---: | :--- |
| **Schema Supabase Multi-Usuário** | Sim | Sim | Sim | 14 tabelas criadas no banco do CursoRadar |
| **Políticas RLS por Usuário** | Sim | Sim | Sim | 23 policies aplicadas; necessita otimização |
| **Seed Inicial Senac SP** | Sim | Sim | Sim | 1 instituição, 6 unidades, 5 cursos cadastrados |
| **Proteção Contra Escalada de Privilégios** | Sim | Não | **Não (P0)** | `handle_new_user` lê role de `raw_user_meta_data` |
| **Interface Next.js 15 (Páginas de Aluno)** | Sim | Sim | Parcial | Telas completas, mas usando mock e `localStorage` |
| **Integração Real Frontend <-> Supabase** | Sim | Parcial | Não | Telas de monitores não chamam o banco de dados |
| **Controle de Acesso Administrativo** | Sim | Parcial | **Não (P1)** | Middleware e Layout não validam role `admin` |
| **Abstração EducationProvider Python** | Sim | Sim | Sim | Providers base e Senac implementados |
| **Resolução de Conflito de Horário/Turno** | Sim | Sim | Sim | 34 testes validam normalização de turno |
| **Motor de Matching e Deduplicação SHA256** | Sim | Sim | Sim | Algoritmo $O(1)$ implementado e testado |
| **Conexão do Worker com Supabase Postgres** | Sim | Não | Não | Worker ainda usa SQLite e listas em memória |
| **Token Linking Telegram via Banco** | Sim | Não | Não | Frontend e Worker ainda operam com mocks |
| **Configuração de Gitignore para Monorepo** | Sim | Não | **Não (P1)** | `.env.local` e `node_modules` desprotegidos |
| **Deploy na Vercel** | Sim | Não | Não | Não vinculado; requer ajuste de root directory |

---

## 9. QUADRO CLASSIFICATÓRIO DE PROBLEMAS (P0 A P3)

### P0 — Crítico (Segurança / Escalada de Privilégios)
* **SEC-01:** **Escalada de Privilégios em `handle_new_user()`**
  - **Arquivo:** `supabase/migrations/20260917000000_init_multiuser_schema.sql:48`
  - **Problema:** A função trigger copia `COALESCE(NEW.raw_user_meta_data->>'role', 'user')` diretamente para `profiles.role`.
  - **Impacto:** Qualquer usuário pode se registrar com `role: "admin"` no payload de cadastro e assumir controle total do banco e de todos os dados da plataforma.
  - **Referência:** Skill `supabase` (Regra: *Never use user_metadata claims in authorization decisions*).
  - **Correção:** Forçar `'user'` incondicionalmente no trigger `handle_new_user()`.

### P1 — Alto (Segurança, Autorização & Higiene)
* **SEC-02:** **Execução Pública de Função `SECURITY DEFINER` (`handle_new_user`)**
  - **Arquivo:** Banco de Dados CursoRadar / `public.handle_new_user`
  - **Problema:** Função `handle_new_user` está exposta como endpoint RPC pública para `anon` e `authenticated`.
  - **Impacto:** Usuários anônimos podem tentar invocar a função diretamente via HTTP API.
  - **Referência:** Skill `supabase` / `supabase db advisors` (`anon_security_definer_function_executable`).
  - **Correção:** `REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM PUBLIC, anon, authenticated;`.
* **SEC-03:** **Ausência de Bloqueio por Role nas Rotas `/admin`**
  - **Arquivo:** `apps/web/src/lib/supabase/middleware.ts:45-53` e `apps/web/src/app/admin/layout.tsx`
  - **Problema:** O middleware valida apenas se o usuário está logado, sem verificar se `role === 'admin'`. O layout é `"use client"` sem barreira de proteção.
  - **Impacto:** Qualquer usuário comum tem acesso visual ao painel de administração.
  - **Correção:** Adicionar verificação de `profile.role === 'admin'` no middleware / server component.
* **SEC-04:** **Segredo Hardcoded como Valor Padrão no Código-Fonte**
  - **Arquivo:** `services/monitor/app/config.py:77`
  - **Problema:** `senac_bolsa_auth: str = Field(default="[REDACTED_AUTH_TOKEN]", ...)`
  - **Impacto:** Exposição de credencial de autorização no repositório Git.
  - **Correção:** Tornar o campo obrigatório via env ou default `None`, exigindo preenchimento via `.env`.
* **GIT-01:** **Falha de Cobertura no `.gitignore` do Monorepo**
  - **Arquivo:** `.gitignore`
  - **Problema:** Não ignora `apps/web/.env.local`, `apps/web/node_modules/` e `apps/web/.next/`.
  - **Impacto:** Risco iminente de commit de chaves de ambiente e gigabytes de arquivos temporários.
  - **Correção:** Adicionar regras para `.env*.local`, `node_modules/` e `.next/`.

### P2 — Médio (Performance, Banco de Dados & Arquitetura)
* **DB-01:** **RLS Evaluates `auth.uid()` por Linha ($O(N)$)**
  - **Arquivo:** `supabase/migrations/20260917000000_init_multiuser_schema.sql` (8 policies)
  - **Problema:** Uso de `auth.uid() = user_id` em vez de `(SELECT auth.uid()) = user_id`.
  - **Referência:** Skill `supabase-postgres-best-practices` (`security-rls-performance.md`).
  - **Impacto:** Queda drástica de performance à medida que o volume de registros crescer.
* **DB-02:** **7 Chaves Estrangeiras sem Índice de Cobertura**
  - **Arquivo:** Tabelas `alerts`, `monitors`, `offers`
  - **Problema:** FKs sem índice (`alerts.change_id`, `alerts.monitor_id`, `alerts.offer_id`, etc.).
  - **Referência:** Skill `supabase-postgres-best-practices` (`schema-foreign-key-indexes.md`).
  - **Impacto:** `JOINs` lentos e locks em operações de deleção em cascata.
* **DB-03:** **Funções de Banco com `search_path` Mutável**
  - **Arquivo:** `is_admin()`, `set_current_timestamp_updated_at()`, `handle_new_user()`
  - **Referência:** Supabase Database Linter (`function_search_path_mutable`).
  - **Correção:** Adicionar `SET search_path = ''` nas definições das funções.
* **APP-01:** **Dashboard e Telas de Monitores Utilizando Mocks / LocalStorage**
  - **Arquivo:** `apps/web/src/app/dashboard/monitors/*`
  - **Problema:** As telas não leem nem gravam dados nas tabelas `public.monitors` do Supabase.
* **APP-02:** **Erro de Atributo na Rota `api/telegram/link-token`**
  - **Arquivo:** `apps/web/src/app/api/telegram/link-token/route.ts:23`
  - **Problema:** Inserção com campo `{ used: false }` (coluna inexistente; o correto é `used_at`).
* **SRV-01:** **Worker Python Opera em SQLite Local e Memória**
  - **Arquivo:** `services/monitor/app/worker.py` e `database.py`
  - **Problema:** O worker não consome nem atualiza as tabelas do Supabase em nuvem.

### P3 — Baixo (Qualidade de Código & Organização)
* **CODE-01:** **Arquivos Duplicados na Raiz do Repositório**
  - **Arquivo:** Diretórios `app/` e `tests/` na raiz
  - **Problema:** Sobras da refatoração inicial que agora residem em `services/monitor/`.
* **VERCEL-01:** **Ajuste de Root Directory para Monorepo na Vercel**
  - **Configuração:** Necessário documentar/definir `apps/web` como Root Directory na Vercel.
* **LINT-01:** **ESLint Não Configurado no Web App**
  - **Arquivo:** `apps/web/package.json`
  - **Problema:** `npm run lint` trava pedindo configuração interativa.

---

## 10. SCORECARD TÉCNICO DO PROJETO

| Dimensão | Nota (0–100) | Justificativa Objetiva |
| :--- | :---: | :--- |
| **Isolamento de Projetos** | **100** | Isolamento total e impecável; Trenex está 100% limpo e intocado. |
| **Supabase (Infraestrutura)** | **85** | Instância saudável, migração versionada aplicada, tipos TypeScript sincronizados. |
| **Segurança** | **45** | Presença de vulnerabilidade P0 (escalada de privilégio via `raw_user_meta_data`) e P1 (admin desprotegido, RPCs públicas). |
| **Row Level Security (RLS)** | **65** | RLS habilitado em 100% das tabelas, mas com subqueries faltantes (`auth.uid()` vs `(select auth.uid())`) e políticas permissivas redundantes. |
| **Banco / PostgreSQL** | **70** | Boa tipagem e constraints, mas possui 7 FKs sem índices e `search_path` mutável nas funções. |
| **Frontend (Interface/UX)** | **88** | 19 rotas, design responsivo moderno com shadcn/ui e Tailwind, compilação com zero erros. |
| **Frontend (Integração de Dados)** | **35** | Quase todo o dashboard opera em mocks e `localStorage`, sem chamadas reais às tabelas do Supabase. |
| **Backend / Worker** | **65** | Lógica de negócio e matching testados (34 testes passando), mas desacoplado do Supabase (opera em SQLite/memória). |
| **Arquitetura Geral** | **70** | Boa separação conceitual em monorepo, mas com resíduos da estrutura anterior na raiz. |
| **Git & Repositório** | **40** | `.gitignore` incompleto para monorepo Next.js, risco de commit de `.env.local` e `node_modules`, sem remote. |
| **Vercel / Deploy** | **55** | App pronto para build, mas não configurado como subdiretório monorepo nem vinculado. |
| **SCORE GERAL** | **65 / 100** | **Base sólida e visualmente madura, porém exigindo blindagem de segurança e integração real com o banco antes de produção.** |

---

## 11. VEREDITO FINAL DA AUDITORIA
- **Interferência no Trenex:** **ZERO / TOTALMENTE LIMPO**.
- **Prontidão do CursoRadar:** **FASE 1 (P0) E FASE 2 (P1) RESOLVIDAS COM SUCESSO**.
- **Ação Imediata:** Aguardar autorização do usuário para início das Fases 3 (P2) e 4 (P3).

---

## 12. STATUS DE REMEDIAÇÃO — FASES 1 (P0) E 2 (P1) CONCLUÍDAS

Em 17/09/2026, com autorização do usuário, foram executadas com sucesso as correções P0 e P1:

| Código | Prioridade | Descrição | Status | Resolução / Evidência |
| :--- | :---: | :--- | :---: | :--- |
| **SEC-01** | **P0** | Escalada de Privilégios no Cadastro (`handle_new_user`) | **RESOLVIDO** | Migration `20260917010000_fix_security_definer_and_privileges.sql` aplicada no CursoRadar. `role = 'user'` forçado; `search_path = public, pg_temp` blindado. Teste automatizado com tentativa de injeção de role admin validado. |
| **SEC-02** | **P1** | Funções de Trigger Expostas via RPC PostgREST | **RESOLVIDO** | Migration `20260917020000_revoke_rpc_public_execution.sql` aplicada. Privilégio `EXECUTE` revogado de `PUBLIC`, `anon` e `authenticated` para `handle_new_user` e `set_current_timestamp_updated_at`. |
| **APP-SEC-01** | **P1** | Área `/admin` Desprotegida no Next.js 15 | **RESOLVIDO** | Middleware do Next.js agora consulta `profiles` no Supabase e bloqueia acessos não-admin. `AdminLayout` convertido para Server Component com `redirect('/login')` e `redirect('/dashboard?error=access_denied')`. Build 19/19 rotas OK. |
| **SEC-03** | **P1** | Credencial Hardcoded em `config.py` e Scrapers | **RESOLVIDO** | Token padrão removido de `services/monitor/app/config.py`, `app/config.py` e scrapers. Desacoplado via env var `SENAC_BOLSA_AUTH`. 34/34 testes Python passando. |
| **GIT-01** | **P1** | Falha de Cobertura no `.gitignore` do Monorepo | **RESOLVIDO** | `.gitignore` expandido com regras para `.env*.local`, `node_modules/`, `.next/`. Auditoria de histórico comprovou que zero segredos foram rastreados pelo Git. |

### Scorecard Técnico Atualizado Pós P0/P1

| Dimensão | Nota Anterior | Nova Nota | Justificativa da Evolução |
| :--- | :---: | :---: | :--- |
| **Isolamento de Projetos** | 100 | **100** | Trenex permanece 100% inativo e intocado |
| **Supabase (Infraestrutura)** | 85 | **90** | Funções de trigger e RLS blindadas contra hijacking |
| **Segurança** | 45 | **90** | P0 e P1 mitigados; role admin blindada e rotas restritas |
| **Row Level Security (RLS)** | 65 | **70** | RPCs indevidas eliminadas |
| **Banco / PostgreSQL** | 70 | **75** | `search_path` seguro fixado nas funções de sistema |
| **Frontend (Interface/UX)** | 88 | **90** | Layout admin e shell agora seguros e dinâmicos |
| **Frontend (Integração de Dados)** | 35 | **35** | Pendente Fase 3 (P2) |
| **Backend / Worker** | 65 | **70** | Credenciais desacopladas, zero secrets em código |
| **Arquitetura Geral** | 70 | **72** | Estrutura de guards server-side e client shell padronizada |
| **Git & Repositório** | 40 | **85** | `.gitignore` blindado, segredos auditados |
| **Vercel / Deploy** | 55 | **55** | Pendente Fase 4 (P3) |
| **SCORE GERAL** | **65 / 100** | **78 / 100** | **Grande avanço em segurança e conformidade arquitetural** |

