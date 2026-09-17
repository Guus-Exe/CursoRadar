# Senac Monitor Multi-User Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the Senac Monitor from a local single-user bot into a complete multi-user web platform with Next.js dashboard, PostgreSQL/Supabase with RLS, multi-user Telegram linking, decoupled matching engine, and scalable worker.

**Architecture:** Monorepo containing `apps/web` (Next.js App Router, Tailwind, shadcn/ui, Supabase Auth/Client), `services/monitor` (Python continuous worker, EducationProvider abstraction, MatchingEngine, Telegram bot & notifier), and `supabase/` (versioned SQL migrations and RLS).

**Tech Stack:** Next.js 15 / React 19, TypeScript, Tailwind CSS, Lucide, Python 3.12+, Supabase (PostgreSQL 15+, Auth, RLS, Realtime), APScheduler, HTTPX, python-telegram-bot, Pytest.

**Spec:** `docs/superpowers/specs/2026-09-17-multiuser-platform-design.md`

## Global Constraints

- Never commit secrets or expose `service_role` key in frontend / browser.
- Preserve existing working components and maintain passing tests throughout (17 baseline tests must never regress).
- Use `EducationProvider` interface so that future providers (Senai, Etec, Fatec) require zero architecture changes.
- Deduplication of checks: an offer is queried only once per cycle regardless of how many users monitor it.
- Deduplication of alerts: fingerprint-based idempotency prevents duplicate user alerts.
- Shift normalization must accurately classify 8h às 12h as Manhã and reconcile any conflicts with schedule hours.

---

### Task 1: Supabase Migrations, Schema & Seed

**Files:**
- Create: `supabase/migrations/20260917000000_init_multiuser_schema.sql`
- Create: `supabase/seed.sql`
- Create: `tests/test_schema.py` or verification script

**Interfaces:**
- Produces: Tables (`profiles`, `telegram_accounts`, `telegram_link_tokens`, `institutions`, `locations`, `courses`, `offers`, `monitors`, `monitor_preferences`, `offer_checks`, `offer_changes`, `alerts`, `worker_health`, `system_errors`) and complete RLS policies.

- [ ] **Step 1: Write SQL migration file with DDL and RLS**
- [ ] **Step 2: Write seed SQL with initial Senac SP institution, Lapa Faustolo unit, and course**
- [ ] **Step 3: Test SQL schema validity using python test with in-memory SQLite / PostgreSQL parser or sqlite compatibility check**
- [ ] **Step 4: Commit schema changes**

---

### Task 2: Refactor Worker Directory & Fix Turno/Horário Inconsistency

**Files:**
- Create: `services/monitor/` structure
- Move/Adapt: `app/` and `tests/` into `services/monitor/`
- Modify: `services/monitor/app/scrapers/offer_parser.py`
- Modify: `services/monitor/app/scrapers/senac.py`
- Modify: `services/monitor/app/config.py`
- Create: `services/monitor/tests/test_shift_normalization.py`

**Interfaces:**
- Produces: `normalize_shift(raw_shift, hours_text)` correctly resolving "8h às 12h" to "Manhã", and removing hardcoded `WSE_BOLSA_AUTH_TOKEN`.
- Consumes: Baseline 17 tests.

- [ ] **Step 1: Write failing test in `test_shift_normalization.py` asserting "8h às 12h" is Manhã even when raw_shift is "NO" or None**
- [ ] **Step 2: Run pytest to verify failure**
- [ ] **Step 3: Update `normalize_shift`, `parse_html_offer`, and `SenacScraper` to handle schedules and env var `SENAC_BOLSA_AUTH`**
- [ ] **Step 4: Run all pytest tests in `services/monitor` to verify all pass**
- [ ] **Step 5: Commit**

---

### Task 3: EducationProvider Abstraction & SenacSPProvider

**Files:**
- Create: `services/monitor/app/providers/base.py`
- Create: `services/monitor/app/providers/senac.py`
- Create: `services/monitor/tests/test_providers.py`

**Interfaces:**
- Produces: `EducationProvider` ABC (`get_locations`, `search_courses`, `discover_offers`, `get_offer_state`) and `SenacSPProvider`.

- [ ] **Step 1: Write failing tests for `EducationProvider` and `SenacSPProvider`**
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement `EducationProvider` and `SenacSPProvider` delegating to `senac_client` / `offer_parser`**
- [ ] **Step 4: Run tests to verify pass**
- [ ] **Step 5: Commit**

---

### Task 4: Matching Engine & Multi-User Deduplication

**Files:**
- Create: `services/monitor/app/matching.py`
- Modify: `services/monitor/app/models.py`
- Create: `services/monitor/tests/test_matching.py`

**Interfaces:**
- Consumes: `OfferState`, `StateDiff`, `OfferChange`, `Monitor`, `MonitorPreference`.
- Produces: `MatchingEngine.match(change, monitors)` returning recipients, generating SHA256 fingerprints, preventing duplicates.

- [ ] **Step 1: Write test for matching with 100 users monitoring 1 opportunity**
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement `MatchingEngine` with preference filtering and fingerprint calculation**
- [ ] **Step 4: Run test to verify 100 matches and duplicate rejection**
- [ ] **Step 5: Commit**

---

### Task 5: Multi-User Telegram Provider & Token Linking

**Files:**
- Modify: `services/monitor/app/notifications/telegram.py`
- Create: `services/monitor/app/telegram_link.py`
- Create: `services/monitor/tests/test_telegram_multiuser.py`

**Interfaces:**
- Produces: `generate_link_token(user_id)`, `validate_and_consume_token(token, chat_id, username, first_name)`.
- Updates: `TelegramProvider.send_to_user(chat_id, message)`.

- [ ] **Step 1: Write tests for link token lifecycle (generation, expiration, single-use, replay protection)**
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement token handling and multi-user telegram command handler**
- [ ] **Step 4: Run tests to verify pass**
- [ ] **Step 5: Commit**

---

### Task 6: Multi-User Worker Orchestration & Heartbeat

**Files:**
- Create: `services/monitor/app/worker.py`
- Modify: `services/monitor/app/main.py`
- Create: `services/monitor/tests/test_worker_health.py`

**Interfaces:**
- Produces: Continuous worker executing 1 check cycle for all tracked offers, matching against monitors, recording `worker_health` heartbeat, and logging errors to `system_errors`.

- [ ] **Step 1: Write tests for worker cycle and health heartbeat**
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement multi-user `CourseWorker` orchestrator**
- [ ] **Step 4: Run test to verify pass**
- [ ] **Step 5: Commit**

---

### Task 7: Next.js Web Application Setup & Layout

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/tailwind.config.ts`
- Create: `apps/web/src/app/layout.tsx`
- Create: `apps/web/src/lib/supabase/client.ts`
- Create: `apps/web/src/lib/supabase/server.ts`
- Create: `apps/web/src/lib/supabase/middleware.ts`
- Create: `apps/web/src/middleware.ts`
- Create: `apps/web/src/components/ui/` (buttons, inputs, cards, tables, badges, dialogs)

**Interfaces:**
- Produces: Base web app with styling, Supabase authentication integration, and route protection.

- [ ] **Step 1: Create Next.js project structure, package.json, and dependencies**
- [ ] **Step 2: Install dependencies with npm**
- [ ] **Step 3: Setup Tailwind CSS and UI component primitives**
- [ ] **Step 4: Setup Supabase SSR client and middleware**
- [ ] **Step 5: Verify build with `npm run build`**
- [ ] **Step 6: Commit**

---

### Task 8: User Dashboard Pages & Cascading Monitor Creation

**Files:**
- Create: `apps/web/src/app/(auth)/login/page.tsx`
- Create: `apps/web/src/app/(auth)/register/page.tsx`
- Create: `apps/web/src/app/dashboard/page.tsx`
- Create: `apps/web/src/app/dashboard/monitors/page.tsx`
- Create: `apps/web/src/app/dashboard/monitors/new/page.tsx`
- Create: `apps/web/src/app/dashboard/alerts/page.tsx`
- Create: `apps/web/src/app/dashboard/settings/telegram/page.tsx`
- Create: `apps/web/src/app/api/telegram/link-token/route.ts`

**Interfaces:**
- Produces: Functional user views for auth, dashboard metrics, cascading monitor creation (Institution $\rightarrow$ Unit $\rightarrow$ Course $\rightarrow$ Shift $\rightarrow$ Preferences), monitor controls, alerts history, and Telegram linking.

- [ ] **Step 1: Implement auth pages (`/login`, `/register`)**
- [ ] **Step 2: Implement `/dashboard` overview**
- [ ] **Step 3: Implement `/dashboard/monitors` and `/dashboard/monitors/new` with cascading dependent dropdowns**
- [ ] **Step 4: Implement `/dashboard/alerts` and `/dashboard/settings/telegram` with link-token API**
- [ ] **Step 5: Verify build with `npm run build`**
- [ ] **Step 6: Commit**

---

### Task 9: Admin Dashboard Pages & Observability

**Files:**
- Create: `apps/web/src/app/admin/layout.tsx`
- Create: `apps/web/src/app/admin/page.tsx`
- Create: `apps/web/src/app/admin/users/page.tsx`
- Create: `apps/web/src/app/admin/offers/page.tsx`
- Create: `apps/web/src/app/admin/monitors/page.tsx`
- Create: `apps/web/src/app/admin/alerts/page.tsx`
- Create: `apps/web/src/app/admin/workers/page.tsx`
- Create: `apps/web/src/app/admin/errors/page.tsx`

**Interfaces:**
- Produces: Secure admin dashboard with role verification (`role === 'admin'`), users table, tracked offers, global monitors, system alerts, worker health heartbeats, and error logs.

- [ ] **Step 1: Implement admin layout with role check**
- [ ] **Step 2: Implement `/admin` metrics overview**
- [ ] **Step 3: Implement `/admin/users`, `/admin/offers`, `/admin/monitors`**
- [ ] **Step 4: Implement `/admin/workers`, `/admin/alerts`, `/admin/errors`**
- [ ] **Step 5: Verify build with `npm run build`**
- [ ] **Step 6: Commit**

---

### Task 10: Docker, Environment Configuration & End-to-End Validation

**Files:**
- Create: `Dockerfile` (updated for `services/monitor`)
- Create: `docker-compose.yml` (orchestrating worker + web + postgres)
- Modify: `.env.example`
- Modify: `README.md`
- Create: `docs/architecture.md`

**Interfaces:**
- Produces: Complete production-ready setup with Docker, comprehensive `.env.example`, updated README, and browser-verified end-to-end user flows.

- [ ] **Step 1: Update Dockerfile and docker-compose.yml**
- [ ] **Step 2: Update `.env.example` with WEB, SUPABASE, TELEGRAM, SENAC, WORKER sections**
- [ ] **Step 3: Test frontend in browser using `agent-browser` (Chrome devtools) across mobile (375px), tablet (768px), desktop (1440px)**
- [ ] **Step 4: Run all Python tests and frontend build to verify zero regressions**
- [ ] **Step 5: Update README.md and commit**
