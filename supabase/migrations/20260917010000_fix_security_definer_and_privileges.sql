-- ==============================================================================
-- CURSORADAR - MIGRAÇÃO DE SEGURANÇA (FASE 1 - P0)
-- Versão: 20260917010000_fix_security_definer_and_privileges.sql
-- Alvo Exclusivo: CursoRadar (ref: rbqqilyupzyibacytdwp)
-- Objetivo: Prevenção de escalada de privilégios e mitigação de search_path hijacking
-- ==============================================================================

-- 1. Atualizar handle_new_user() para forçar role = 'user'
-- Impede que parâmetros como raw_user_meta_data->>'role' = 'admin' concedam privilégios elevados.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER 
LANGUAGE plpgsql 
SECURITY DEFINER 
SET search_path = public, pg_temp
AS $$
BEGIN
  INSERT INTO public.profiles (id, email, name, role, status)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1)),
    'user', -- FORÇADO: Papel é sempre 'user' no auto-signup
    'active'
  )
  ON CONFLICT (id) DO UPDATE SET
    email = EXCLUDED.email,
    name = COALESCE(public.profiles.name, EXCLUDED.name);
  RETURN NEW;
END;
$$;

-- 2. Corrigir search_path na função is_admin()
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN 
LANGUAGE sql 
SECURITY DEFINER 
STABLE
SET search_path = public, pg_temp
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid() AND role = 'admin' AND status = 'active'
  );
$$;

-- 3. Corrigir search_path na função set_current_timestamp_updated_at()
CREATE OR REPLACE FUNCTION public.set_current_timestamp_updated_at()
RETURNS TRIGGER 
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;
