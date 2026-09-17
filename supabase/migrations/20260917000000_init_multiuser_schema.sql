-- ==============================================================================
-- SENAC MONITOR: SCHEMA MULTIUSUÁRIO & ROW LEVEL SECURITY
-- Versão: 20260917000000_init_multiuser_schema.sql
-- ==============================================================================

-- 1. Extensões
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Função trigger para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION public.set_current_timestamp_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- 2. TABELAS DE AUTENTICAÇÃO E PERFIS
-- ==============================================================================

-- Tabela de perfis públicos associados aos usuários do auth.users
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    name TEXT,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER handle_updated_at_profiles
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.set_current_timestamp_updated_at();

-- Trigger para criar profile automaticamente no Supabase Auth signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, name, role, status)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1)),
    COALESCE(NEW.raw_user_meta_data->>'role', 'user'),
    'active'
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ==============================================================================
-- 3. INTEGRAÇÃO TELEGRAM MULTIUSUÁRIO
-- ==============================================================================

-- Contas do Telegram vinculadas
CREATE TABLE IF NOT EXISTS public.telegram_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE UNIQUE,
    telegram_chat_id TEXT NOT NULL UNIQUE,
    telegram_username TEXT,
    telegram_first_name TEXT,
    verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER handle_updated_at_telegram_accounts
    BEFORE UPDATE ON public.telegram_accounts
    FOR EACH ROW
    EXECUTE FUNCTION public.set_current_timestamp_updated_at();

CREATE INDEX IF NOT EXISTS idx_telegram_accounts_chat_id ON public.telegram_accounts(telegram_chat_id);
CREATE INDEX IF NOT EXISTS idx_telegram_accounts_user_id ON public.telegram_accounts(user_id);

-- Tokens seguros e temporários para vinculação
CREATE TABLE IF NOT EXISTS public.telegram_link_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_telegram_link_tokens_token ON public.telegram_link_tokens(token);
CREATE INDEX IF NOT EXISTS idx_telegram_link_tokens_user ON public.telegram_link_tokens(user_id);

-- ==============================================================================
-- 4. CATÁLOGO EDUCACIONAL (INSTITUIÇÕES, UNIDADES, CURSOS)
-- ==============================================================================

-- Instituições educacionais (Senac, Senai, Etec, Fatec)
CREATE TABLE IF NOT EXISTS public.institutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'SP',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unidades / Campi / Polos
CREATE TABLE IF NOT EXISTS public.locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID NOT NULL REFERENCES public.institutions(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'SP',
    external_id TEXT, -- ID no sistema da instituição (ex: categoryId Liferay 40814)
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_institution_location_slug UNIQUE (institution_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_locations_institution ON public.locations(institution_id);
CREATE INDEX IF NOT EXISTS idx_locations_city ON public.locations(city);

-- Cursos oferecidos
CREATE TABLE IF NOT EXISTS public.courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID NOT NULL REFERENCES public.institutions(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    category TEXT DEFAULT 'cursos-tecnicos',
    external_id TEXT, -- ID ou código FT do curso (ex: articleId ou codigoFT)
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_institution_course_slug UNIQUE (institution_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_courses_institution ON public.courses(institution_id);

-- ==============================================================================
-- 5. OFERTAS COLETADAS (NÃO PERTENCEM AO USUÁRIO)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID NOT NULL REFERENCES public.institutions(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES public.courses(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES public.locations(id) ON DELETE CASCADE,
    external_offer_id TEXT NOT NULL,
    shift TEXT NOT NULL, -- Noturno, Manhã, Tarde, Integral
    url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Indisponível',
    bolsa_disponivel BOOLEAN NOT NULL DEFAULT FALSE,
    inscricao_disponivel BOOLEAN NOT NULL DEFAULT FALSE,
    current_state_json JSONB,
    current_state_hash TEXT,
    first_detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_institution_offer_id UNIQUE (institution_id, external_offer_id)
);

CREATE INDEX IF NOT EXISTS idx_offers_lookup ON public.offers(institution_id, location_id, course_id, shift);
CREATE INDEX IF NOT EXISTS idx_offers_last_checked ON public.offers(last_checked_at);
CREATE INDEX IF NOT EXISTS idx_offers_external_id ON public.offers(external_offer_id);

-- ==============================================================================
-- 6. MONITORAMENTOS DO USUÁRIO & PREFERÊNCIAS
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.monitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    institution_id UUID NOT NULL REFERENCES public.institutions(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES public.locations(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES public.courses(id) ON DELETE CASCADE,
    shift TEXT, -- NULL indica qualquer turno
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER handle_updated_at_monitors
    BEFORE UPDATE ON public.monitors
    FOR EACH ROW
    EXECUTE FUNCTION public.set_current_timestamp_updated_at();

CREATE INDEX IF NOT EXISTS idx_monitors_user_id ON public.monitors(user_id);
CREATE INDEX IF NOT EXISTS idx_monitors_match ON public.monitors(institution_id, location_id, course_id, active);

CREATE TABLE IF NOT EXISTS public.monitor_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    monitor_id UUID NOT NULL REFERENCES public.monitors(id) ON DELETE CASCADE UNIQUE,
    notify_scholarship BOOLEAN NOT NULL DEFAULT TRUE,
    notify_paid BOOLEAN NOT NULL DEFAULT TRUE,
    notify_enrollment_open BOOLEAN NOT NULL DEFAULT TRUE,
    notify_new_offer BOOLEAN NOT NULL DEFAULT TRUE,
    notify_new_class BOOLEAN NOT NULL DEFAULT TRUE,
    notify_date_changes BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ==============================================================================
-- 7. EVENTOS, CHECKS E HISTÓRICO DE MUDANÇAS
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.offer_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    offer_id UUID NOT NULL REFERENCES public.offers(id) ON DELETE CASCADE,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_success BOOLEAN NOT NULL,
    status_code INTEGER NOT NULL DEFAULT 200,
    state_json JSONB,
    diff_json JSONB,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_offer_checks_offer ON public.offer_checks(offer_id, checked_at DESC);

CREATE TABLE IF NOT EXISTS public.offer_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    offer_id UUID NOT NULL REFERENCES public.offers(id) ON DELETE CASCADE,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    change_type TEXT NOT NULL,
    previous_state_json JSONB,
    current_state_json JSONB,
    reasons TEXT[],
    is_actionable BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_offer_changes_offer ON public.offer_changes(offer_id, detected_at DESC);

-- ==============================================================================
-- 8. ALERTAS ENVIADOS E DEDUPLICAÇÃO
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    monitor_id UUID NOT NULL REFERENCES public.monitors(id) ON DELETE CASCADE,
    offer_id UUID REFERENCES public.offers(id) ON DELETE SET NULL,
    change_id UUID REFERENCES public.offer_changes(id) ON DELETE SET NULL,
    alert_type TEXT NOT NULL,
    fingerprint TEXT NOT NULL UNIQUE,
    channel TEXT NOT NULL DEFAULT 'telegram',
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered BOOLEAN NOT NULL DEFAULT TRUE,
    error_message TEXT,
    message_content TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alerts_user ON public.alerts(user_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_fingerprint ON public.alerts(fingerprint);

-- ==============================================================================
-- 9. OBSERVABILIDADE, WORKERS E ERROS
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.worker_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id TEXT NOT NULL,
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_cycle_at TIMESTAMPTZ,
    cycle_duration_seconds NUMERIC(8,2),
    offers_checked INTEGER DEFAULT 0,
    offers_succeeded INTEGER DEFAULT 0,
    offers_failed INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'healthy',
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_worker_health_heartbeat ON public.worker_health(worker_id, heartbeat_at DESC);

CREATE TABLE IF NOT EXISTS public.system_errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,
    error_type TEXT NOT NULL,
    message TEXT NOT NULL,
    stack_trace TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_errors_created ON public.system_errors(created_at DESC);

-- ==============================================================================
-- 10. ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================

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

-- Função auxiliar para checagem se o usuário atual é admin
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid() AND role = 'admin' AND status = 'active'
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- PROFILES
CREATE POLICY "Users can read own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = id OR is_admin());

CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id AND role = 'user');

CREATE POLICY "Admins full access on profiles" ON public.profiles
    FOR ALL USING (is_admin());

-- TELEGRAM ACCOUNTS
CREATE POLICY "Users can view own telegram account" ON public.telegram_accounts
    FOR SELECT USING (auth.uid() = user_id OR is_admin());

CREATE POLICY "Users can delete own telegram account" ON public.telegram_accounts
    FOR DELETE USING (auth.uid() = user_id OR is_admin());

CREATE POLICY "Admins full access on telegram accounts" ON public.telegram_accounts
    FOR ALL USING (is_admin());

-- TELEGRAM LINK TOKENS
CREATE POLICY "Users manage own link tokens" ON public.telegram_link_tokens
    FOR ALL USING (auth.uid() = user_id OR is_admin());

-- INSTITUTIONS, LOCATIONS, COURSES (Catálogo)
CREATE POLICY "Public read institutions" ON public.institutions
    FOR SELECT USING (TRUE);

CREATE POLICY "Public read locations" ON public.locations
    FOR SELECT USING (TRUE);

CREATE POLICY "Public read courses" ON public.courses
    FOR SELECT USING (TRUE);

CREATE POLICY "Admin manage institutions" ON public.institutions
    FOR ALL USING (is_admin());

CREATE POLICY "Admin manage locations" ON public.locations
    FOR ALL USING (is_admin());

CREATE POLICY "Admin manage courses" ON public.courses
    FOR ALL USING (is_admin());

-- OFFERS
CREATE POLICY "Public read offers" ON public.offers
    FOR SELECT USING (TRUE);

CREATE POLICY "Admin manage offers" ON public.offers
    FOR ALL USING (is_admin());

-- MONITORS
CREATE POLICY "Users manage own monitors" ON public.monitors
    FOR ALL USING (auth.uid() = user_id OR is_admin());

-- MONITOR PREFERENCES
CREATE POLICY "Users manage preferences of own monitors" ON public.monitor_preferences
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.monitors
            WHERE monitors.id = monitor_preferences.monitor_id
            AND (monitors.user_id = auth.uid() OR is_admin())
        )
    );

-- ALERTS
CREATE POLICY "Users read own alerts" ON public.alerts
    FOR SELECT USING (auth.uid() = user_id OR is_admin());

CREATE POLICY "Admin full access on alerts" ON public.alerts
    FOR ALL USING (is_admin());

-- OBSERVABILIDADE (ADMIN ONLY)
CREATE POLICY "Admin view checks" ON public.offer_checks
    FOR SELECT USING (is_admin());

CREATE POLICY "Admin view changes" ON public.offer_changes
    FOR SELECT USING (is_admin());

CREATE POLICY "Admin view worker health" ON public.worker_health
    FOR SELECT USING (is_admin());

CREATE POLICY "Admin view system errors" ON public.system_errors
    FOR SELECT USING (is_admin());
