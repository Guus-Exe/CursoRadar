-- ==============================================================================
-- CURSORADAR MULTI-PROVIDER ARCHITECTURE MIGRATION
-- Migration: 20260917050000_multi_provider_schema.sql
-- Project: CursoRadar (rbqqilyupzyibacytdwp)
-- ==============================================================================

-- 1. TABELA DE PROVEDORES DE COLETA (FONTES)
CREATE TABLE IF NOT EXISTS public.providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    health_status TEXT NOT NULL DEFAULT 'unknown' 
        CONSTRAINT chk_providers_health_status CHECK (health_status IN ('healthy', 'degraded', 'offline', 'maintenance', 'unknown')),
    website_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trigger de updated_at para providers
CREATE TRIGGER handle_updated_at_providers
    BEFORE UPDATE ON public.providers
    FOR EACH ROW
    EXECUTE FUNCTION public.set_current_timestamp_updated_at();

-- Índices e RLS de providers
CREATE INDEX IF NOT EXISTS idx_providers_slug ON public.providers(slug);
CREATE INDEX IF NOT EXISTS idx_providers_enabled ON public.providers(enabled);

ALTER TABLE public.providers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated read on providers"
    ON public.providers
    FOR SELECT
    TO authenticated
    USING (true);

-- Seed inicial de provedores
INSERT INTO public.providers (slug, name, enabled, health_status, website_url)
VALUES 
    ('senac_sp', 'Senac São Paulo', TRUE, 'healthy', 'https://www.sp.senac.br'),
    ('senai_sp', 'SENAI São Paulo', FALSE, 'unknown', 'https://sp.senai.br'),
    ('cps_etec', 'ETEC — Centro Paula Souza', FALSE, 'unknown', 'https://www.cps.sp.gov.br')
ON CONFLICT (slug) DO UPDATE 
SET 
    name = EXCLUDED.name,
    enabled = EXCLUDED.enabled,
    health_status = EXCLUDED.health_status,
    website_url = EXCLUDED.website_url;

-- 2. RELACIONAMENTO MONITORES <-> PROVEDORES (N:N)
CREATE TABLE IF NOT EXISTS public.monitor_providers (
    monitor_id UUID NOT NULL REFERENCES public.monitors(id) ON DELETE CASCADE,
    provider_id UUID NOT NULL REFERENCES public.providers(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (monitor_id, provider_id)
);

-- Índice cobrindo a FK provider_id
CREATE INDEX IF NOT EXISTS idx_monitor_providers_provider_id 
    ON public.monitor_providers(provider_id);

ALTER TABLE public.monitor_providers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own monitor_providers"
    ON public.monitor_providers
    FOR ALL
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.monitors m
            WHERE m.id = monitor_providers.monitor_id
            AND m.user_id = (SELECT auth.uid())
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.monitors m
            WHERE m.id = monitor_providers.monitor_id
            AND m.user_id = (SELECT auth.uid())
        )
    );

-- 3. FLEXIBILIZAÇÃO E EXPANSÃO DA TABELA DE MONITORES
ALTER TABLE public.monitors ALTER COLUMN institution_id DROP NOT NULL;
ALTER TABLE public.monitors ALTER COLUMN location_id DROP NOT NULL;
ALTER TABLE public.monitors ALTER COLUMN course_id DROP NOT NULL;

ALTER TABLE public.monitors 
    ADD COLUMN IF NOT EXISTS query_text TEXT,
    ADD COLUMN IF NOT EXISTS all_providers BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS city TEXT,
    ADD COLUMN IF NOT EXISTS state TEXT NOT NULL DEFAULT 'SP',
    ADD COLUMN IF NOT EXISTS modality TEXT NOT NULL DEFAULT 'all',
    ADD COLUMN IF NOT EXISTS opportunity_type TEXT NOT NULL DEFAULT 'all',
    ADD COLUMN IF NOT EXISTS notify_channels TEXT[] NOT NULL DEFAULT ARRAY['dashboard', 'telegram'];

CREATE INDEX IF NOT EXISTS idx_monitors_active_all_providers 
    ON public.monitors(active, all_providers);

-- 4. FLEXIBILIZAÇÃO E EXPANSÃO DA TABELA DE OFERTAS
ALTER TABLE public.offers ALTER COLUMN institution_id DROP NOT NULL;
ALTER TABLE public.offers ALTER COLUMN location_id DROP NOT NULL;
ALTER TABLE public.offers ALTER COLUMN course_id DROP NOT NULL;
ALTER TABLE public.offers ALTER COLUMN external_offer_id DROP NOT NULL;
ALTER TABLE public.offers ALTER COLUMN url DROP NOT NULL;

-- provider_id com ON DELETE RESTRICT para segurança de integridade histórica
ALTER TABLE public.offers
    ADD COLUMN IF NOT EXISTS provider_id UUID REFERENCES public.providers(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS external_id TEXT,
    ADD COLUMN IF NOT EXISTS title TEXT,
    ADD COLUMN IF NOT EXISTS source_url TEXT,
    ADD COLUMN IF NOT EXISTS raw_data JSONB,
    ADD COLUMN IF NOT EXISTS modality TEXT NOT NULL DEFAULT 'presencial',
    ADD COLUMN IF NOT EXISTS city TEXT,
    ADD COLUMN IF NOT EXISTS state TEXT NOT NULL DEFAULT 'SP',
    ADD COLUMN IF NOT EXISTS price NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS is_free BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS has_scholarship BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS fingerprint TEXT;

-- Retrocompatibilidade e sincronização das ofertas existentes do Senac
UPDATE public.offers 
SET 
    provider_id = (SELECT id FROM public.providers WHERE slug = 'senac_sp'),
    external_id = COALESCE(external_id, external_offer_id),
    source_url = COALESCE(source_url, url),
    title = COALESCE(title, (SELECT name FROM public.courses WHERE id = offers.course_id)),
    has_scholarship = COALESCE(has_scholarship, bolsa_disponivel)
WHERE provider_id IS NULL;

-- 5. CONSTRAINTS E ÍNDICES DE PERFORMANCE / INTEGRIDADE
CREATE INDEX IF NOT EXISTS idx_offers_provider_id 
    ON public.offers(provider_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_offers_provider_external_id 
    ON public.offers(provider_id, external_id) 
    WHERE external_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_offers_provider_fingerprint 
    ON public.offers(provider_id, fingerprint) 
    WHERE external_id IS NULL AND fingerprint IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_offers_search_lookup 
    ON public.offers(provider_id, city, modality, active);
