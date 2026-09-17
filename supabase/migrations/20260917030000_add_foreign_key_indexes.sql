-- ==============================================================================
-- CURSORADAR - OTIMIZAÇÃO DE BANCO (FASE 3 - P2 / ONDA 1 - TASK 6)
-- Versão: 20260917030000_add_foreign_key_indexes.sql
-- Alvo Exclusivo: CursoRadar (ref: rbqqilyupzyibacytdwp)
-- Objetivo: Criação de índices de cobertura para as 7 Chaves Estrangeiras (FKs)
-- ==============================================================================

-- 1. Tabela public.offers
CREATE INDEX IF NOT EXISTS idx_offers_course_id ON public.offers(course_id);
CREATE INDEX IF NOT EXISTS idx_offers_location_id ON public.offers(location_id);

-- 2. Tabela public.monitors
CREATE INDEX IF NOT EXISTS idx_monitors_course_id ON public.monitors(course_id);
CREATE INDEX IF NOT EXISTS idx_monitors_location_id ON public.monitors(location_id);

-- 3. Tabela public.alerts
CREATE INDEX IF NOT EXISTS idx_alerts_change_id ON public.alerts(change_id);
CREATE INDEX IF NOT EXISTS idx_alerts_monitor_id ON public.alerts(monitor_id);
CREATE INDEX IF NOT EXISTS idx_alerts_offer_id ON public.alerts(offer_id);
