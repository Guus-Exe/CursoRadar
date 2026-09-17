-- ==============================================================================
-- SENAC MONITOR: DADOS DE SEED INICIAIS
-- ==============================================================================

-- 1. Instituições
INSERT INTO public.institutions (id, slug, name, state, active)
VALUES 
    ('11111111-1111-1111-1111-111111111111', 'senac-sp', 'Senac São Paulo', 'SP', TRUE)
ON CONFLICT (slug) DO NOTHING;

-- 2. Unidades (Senac SP)
INSERT INTO public.locations (id, institution_id, name, slug, city, state, external_id, active)
VALUES
    ('22222222-2222-2222-2222-222222222221', '11111111-1111-1111-1111-111111111111', 'Senac Lapa Faustolo', 'senac-lapa-faustolo', 'São Paulo', 'SP', '40814', TRUE),
    ('22222222-2222-2222-2222-222222222222', '11111111-1111-1111-1111-111111111111', 'Senac Lapa Tito', 'senac-lapa-tito', 'São Paulo', 'SP', '40815', TRUE),
    ('22222222-2222-2222-2222-222222222223', '11111111-1111-1111-1111-111111111111', 'Senac Tiradentes', 'senac-tiradentes', 'São Paulo', 'SP', '40816', TRUE),
    ('22222222-2222-2222-2222-222222222224', '11111111-1111-1111-1111-111111111111', 'Senac Campinas', 'senac-campinas', 'Campinas', 'SP', '40820', TRUE),
    ('22222222-2222-2222-2222-222222222225', '11111111-1111-1111-1111-111111111111', 'Senac Santos', 'senac-santos', 'Santos', 'SP', '40825', TRUE),
    ('22222222-2222-2222-2222-222222222226', '11111111-1111-1111-1111-111111111111', 'Senac São José dos Campos', 'senac-sao-jose-dos-campos', 'São José dos Campos', 'SP', '40830', TRUE)
ON CONFLICT (institution_id, slug) DO NOTHING;

-- 3. Cursos (Senac SP)
INSERT INTO public.courses (id, institution_id, name, slug, category, external_id, active)
VALUES
    ('33333333-3333-3333-3333-333333333331', '11111111-1111-1111-1111-111111111111', 'Técnico em Modelagem do Vestuário', 'curso-tecnico-em-modelagem-do-vestuario', 'cursos-tecnicos', '52620802', TRUE),
    ('33333333-3333-3333-3333-333333333332', '11111111-1111-1111-1111-111111111111', 'Técnico em Informática', 'curso-tecnico-em-informatica', 'cursos-tecnicos', '52620810', TRUE),
    ('33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111', 'Técnico em Administração', 'curso-tecnico-em-administracao', 'cursos-tecnicos', '52620820', TRUE),
    ('33333333-3333-3333-3333-333333333334', '11111111-1111-1111-1111-111111111111', 'Técnico em Enfermagem', 'curso-tecnico-em-enfermagem', 'cursos-tecnicos', '52620830', TRUE),
    ('33333333-3333-3333-3333-333333333335', '11111111-1111-1111-1111-111111111111', 'Técnico em Design de Interiores', 'curso-tecnico-em-design-de-interiores', 'cursos-tecnicos', '52620840', TRUE)
ON CONFLICT (institution_id, slug) DO NOTHING;

-- 4. Oferta de Referência (Senac Lapa Faustolo - Modelagem do Vestuário - Noturno)
INSERT INTO public.offers (
    id,
    institution_id,
    course_id,
    location_id,
    external_offer_id,
    shift,
    url,
    status,
    bolsa_disponivel,
    inscricao_disponivel,
    first_detected_at,
    last_checked_at,
    active
)
VALUES (
    '44444444-4444-4444-4444-444444444441',
    '11111111-1111-1111-1111-111111111111',
    '33333333-3333-3333-3333-333333333331',
    '22222222-2222-2222-2222-222222222221',
    '9900357333',
    'Noturno',
    'https://www.sp.senac.br/senac-lapa-faustolo/cursos-tecnicos/curso-tecnico-em-modelagem-do-vestuario?bolsa=true&oferta=9900357333',
    'Sem vagas disponíveis (Aguardando abertura/Interesse)',
    FALSE,
    FALSE,
    NOW(),
    NOW(),
    TRUE
)
ON CONFLICT (institution_id, external_offer_id) DO NOTHING;
