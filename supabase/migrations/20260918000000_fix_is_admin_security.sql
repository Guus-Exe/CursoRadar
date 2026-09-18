-- ==============================================================================
-- CURSORADAR - MIGRAÇÃO DE SEGURAR (SECURITY ADVISOR)
-- Versão: 20260918000000_fix_is_admin_security.sql
-- Alvo Exclusivo: CursoRadar (ref: rbqqilyupzyibacytdwp)
-- Objetivo: Resolver warning authenticated_security_definer_function_executable
--           convertendo public.is_admin() para SECURITY INVOKER.
-- ==============================================================================

-- 1. Atualizar public.is_admin() para SECURITY INVOKER
-- Como a função apenas consulta public.profiles onde id = auth.uid(),
-- e a política de profiles permite que qualquer usuário autenticado leia
-- seu próprio perfil, a função não requer privilégios elevados de superusuário.
-- A conversão para SECURITY INVOKER elimina o risco de execução com privilégios
-- do criador via PostgREST RPC, satisfazendo a recomendação do Security Advisor.
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN 
LANGUAGE sql 
SECURITY INVOKER 
STABLE
SET search_path = public, pg_temp
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid() AND role = 'admin' AND status = 'active'
  );
$$;

-- 2. Restringir privilégios de execução: revogar de anon e PUBLIC, permitir authenticated e service_role
REVOKE ALL ON FUNCTION public.is_admin() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.is_admin() TO authenticated, service_role;
