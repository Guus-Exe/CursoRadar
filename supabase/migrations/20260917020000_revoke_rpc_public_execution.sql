-- ==============================================================================
-- CURSORADAR - MIGRAÇÃO DE SEGURANÇA (FASE 2 - P1)
-- Versão: 20260917020000_revoke_rpc_public_execution.sql
-- Alvo Exclusivo: CursoRadar (ref: rbqqilyupzyibacytdwp)
-- Objetivo: Revogação de execução pública em funções de trigger/internas
-- ==============================================================================

-- 1. Revogar execução pública da função de trigger handle_new_user()
REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM anon;
REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM authenticated;

-- Garantir acesso apenas para os papéis de serviço e administração do sistema
GRANT EXECUTE ON FUNCTION public.handle_new_user() TO postgres, supabase_auth_admin, service_role;

-- 2. Revogar execução pública da função de trigger set_current_timestamp_updated_at()
REVOKE EXECUTE ON FUNCTION public.set_current_timestamp_updated_at() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.set_current_timestamp_updated_at() FROM anon;

-- Manter execução para authenticated/service_role/postgres
GRANT EXECUTE ON FUNCTION public.set_current_timestamp_updated_at() TO postgres, authenticated, service_role;

-- 3. Revogar execução anônima de is_admin()
REVOKE EXECUTE ON FUNCTION public.is_admin() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.is_admin() FROM anon;
GRANT EXECUTE ON FUNCTION public.is_admin() TO authenticated, postgres, service_role;
