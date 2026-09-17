-- ==============================================================================
-- CURSORADAR - OTIMIZAÇÃO DE RLS (FASE 3 - P2 / ONDA 1 - TASK 7)
-- Versão: 20260917040000_optimize_rls_policies.sql
-- Alvo Exclusivo: CursoRadar (ref: rbqqilyupzyibacytdwp)
-- Objetivo: Otimização de InitPlan ((SELECT auth.uid())) e restrição a authenticated
-- ==============================================================================

-- 1. PROFILES
DROP POLICY IF EXISTS "Users can read own profile" ON public.profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;
DROP POLICY IF EXISTS "Admins full access on profiles" ON public.profiles;

CREATE POLICY "Users can read own profile" ON public.profiles
    FOR SELECT TO authenticated
    USING (((SELECT auth.uid()) = id) OR is_admin());

CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE TO authenticated
    USING ((SELECT auth.uid()) = id)
    WITH CHECK (((SELECT auth.uid()) = id) AND role = 'user');

CREATE POLICY "Admins full access on profiles" ON public.profiles
    FOR ALL TO authenticated
    USING (is_admin())
    WITH CHECK (is_admin());

-- 2. TELEGRAM LINK TOKENS
DROP POLICY IF EXISTS "Users manage own link tokens" ON public.telegram_link_tokens;

CREATE POLICY "Users manage own link tokens" ON public.telegram_link_tokens
    FOR ALL TO authenticated
    USING (((SELECT auth.uid()) = user_id) OR is_admin())
    WITH CHECK (((SELECT auth.uid()) = user_id) OR is_admin());

-- 3. TELEGRAM ACCOUNTS
DROP POLICY IF EXISTS "Users can view own telegram account" ON public.telegram_accounts;
DROP POLICY IF EXISTS "Users can delete own telegram account" ON public.telegram_accounts;
DROP POLICY IF EXISTS "Admins full access on telegram accounts" ON public.telegram_accounts;

CREATE POLICY "Users can view own telegram account" ON public.telegram_accounts
    FOR SELECT TO authenticated
    USING (((SELECT auth.uid()) = user_id) OR is_admin());

CREATE POLICY "Users can delete own telegram account" ON public.telegram_accounts
    FOR DELETE TO authenticated
    USING (((SELECT auth.uid()) = user_id) OR is_admin());

CREATE POLICY "Admins full access on telegram accounts" ON public.telegram_accounts
    FOR ALL TO authenticated
    USING (is_admin())
    WITH CHECK (is_admin());

-- 4. MONITORS
DROP POLICY IF EXISTS "Users manage own monitors" ON public.monitors;

CREATE POLICY "Users manage own monitors" ON public.monitors
    FOR ALL TO authenticated
    USING (((SELECT auth.uid()) = user_id) OR is_admin())
    WITH CHECK (((SELECT auth.uid()) = user_id) OR is_admin());

-- 5. MONITOR PREFERENCES
DROP POLICY IF EXISTS "Users manage preferences of own monitors" ON public.monitor_preferences;

CREATE POLICY "Users manage preferences of own monitors" ON public.monitor_preferences
    FOR ALL TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.monitors
            WHERE monitors.id = monitor_preferences.monitor_id
            AND (((SELECT auth.uid()) = monitors.user_id) OR is_admin())
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.monitors
            WHERE monitors.id = monitor_preferences.monitor_id
            AND (((SELECT auth.uid()) = monitors.user_id) OR is_admin())
        )
    );

-- 6. ALERTS
DROP POLICY IF EXISTS "Users read own alerts" ON public.alerts;
DROP POLICY IF EXISTS "Admin full access on alerts" ON public.alerts;

CREATE POLICY "Users read own alerts" ON public.alerts
    FOR SELECT TO authenticated
    USING (((SELECT auth.uid()) = user_id) OR is_admin());

CREATE POLICY "Admin full access on alerts" ON public.alerts
    FOR ALL TO authenticated
    USING (is_admin())
    WITH CHECK (is_admin());

-- 7. TABELAS DE ADMINISTRAÇÃO E OBSERVABILIDADE
DROP POLICY IF EXISTS "Admin view checks" ON public.offer_checks;
CREATE POLICY "Admin view checks" ON public.offer_checks
    FOR SELECT TO authenticated
    USING (is_admin());

DROP POLICY IF EXISTS "Admin view changes" ON public.offer_changes;
CREATE POLICY "Admin view changes" ON public.offer_changes
    FOR SELECT TO authenticated
    USING (is_admin());

DROP POLICY IF EXISTS "Admin view worker health" ON public.worker_health;
CREATE POLICY "Admin view worker health" ON public.worker_health
    FOR SELECT TO authenticated
    USING (is_admin());

DROP POLICY IF EXISTS "Admin view system errors" ON public.system_errors;
CREATE POLICY "Admin view system errors" ON public.system_errors
    FOR SELECT TO authenticated
    USING (is_admin());

-- 8. GESTÃO DE CATÁLOGO (ADMIN)
DROP POLICY IF EXISTS "Admin manage institutions" ON public.institutions;
CREATE POLICY "Admin manage institutions" ON public.institutions
    FOR ALL TO authenticated
    USING (is_admin())
    WITH CHECK (is_admin());

DROP POLICY IF EXISTS "Admin manage locations" ON public.locations;
CREATE POLICY "Admin manage locations" ON public.locations
    FOR ALL TO authenticated
    USING (is_admin())
    WITH CHECK (is_admin());

DROP POLICY IF EXISTS "Admin manage courses" ON public.courses;
CREATE POLICY "Admin manage courses" ON public.courses
    FOR ALL TO authenticated
    USING (is_admin())
    WITH CHECK (is_admin());

DROP POLICY IF EXISTS "Admin manage offers" ON public.offers;
CREATE POLICY "Admin manage offers" ON public.offers
    FOR ALL TO authenticated
    USING (is_admin())
    WITH CHECK (is_admin());
