"""Comprehensive automated test suite for Senac SP technical courses search and provider.

Covers:
1. Dynamic search by technical course.
2. Course absent from old hardcoded catalog ("Técnico em Redes de Computadores").
3. Ranking and relevance scoring (matching query vs title vs slug).
4. Removal of Modelagem fallback (explicit failure when var data is missing).
5. Search error handling and diagnostic metadata.
6. Differentiation between:
   - COURSE_NOT_FOUND
   - UNSUPPORTED_COURSE_TYPE
   - NO_CLASSES_FOUND
   - CLASSES_FOUND_NO_AVAILABILITY
   - AVAILABLE_OFFERS_FOUND
7. /check using MatchingEngine and formatting distinct messages.
8. Real query_text propagation from monitor to provider.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import httpx

from app.matching import MatchingEngine, UserMonitor
from app.models import OfferState
from app.monitors_repo import SupabaseMonitorRepository
from app.telegram_link import TelegramLinkManager
from app.providers.base import CourseData, NormalizedOffer, ProviderSearchResult, SearchStatus
from app.providers.senac import SenacSPProvider
from app.scrapers.senac import (
    SenacScraper,
    rank_best_course,
)
from app.worker import CourseWorker


# =========================================================================
# 1 & 2: Dynamic Search & Course absent from old hardcoded catalog
# =========================================================================

@pytest.mark.asyncio
async def test_dynamic_search_finds_redes_not_in_old_catalog():
    """Verify that 'Técnico em Redes de Computadores' (absent from old mock catalog)
    is found dynamically via SenacSPProvider."""
    mock_courses = [
        CourseData(
            id="38786021",
            name="Técnico em Redes de Computadores",
            slug="cursos-tecnicos/curso-tecnico-em-redes-de-computadores",
            category="cursos-tecnicos",
            external_id="38786021",
        ),
        CourseData(
            id="55555",
            name="Assistente de Suporte e Manutenção em Redes",
            slug="cursos-livres/curso-de-assistente-em-redes",
            category="cursos-livres",
            external_id="55555",
        ),
    ]

    provider = SenacSPProvider()

    with patch.object(provider.scraper, "search_courses_api", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_courses

        courses = await provider.search_courses("redes de computadores")

        assert len(courses) == 2
        redes = next(c for c in courses if c.external_id == "38786021")
        assert redes.name == "Técnico em Redes de Computadores"
        assert redes.category == "cursos-tecnicos"
        assert redes.slug == "cursos-tecnicos/curso-tecnico-em-redes-de-computadores"


# =========================================================================
# 3: Ranking and Relevance Scorer
# =========================================================================

def test_rank_best_course_selects_most_relevant_technical_course():
    """Ensure candidate ranking prefers exact technical course over partial free course."""
    candidates = [
        CourseData(
            id="1001",
            name="Assistente de Segurança em Redes de Computadores",
            slug="cursos-livres/curso-assistente-seguranca",
            category="cursos-livres",
            external_id="1001",
        ),
        CourseData(
            id="38786021",
            name="Técnico em Redes de Computadores",
            slug="cursos-tecnicos/curso-tecnico-em-redes-de-computadores",
            category="cursos-tecnicos",
            external_id="38786021",
        ),
        CourseData(
            id="1002",
            name="Administração de Redes Linux",
            slug="cursos-livres/curso-redes-linux",
            category="cursos-livres",
            external_id="1002",
        ),
    ]

    best, score = rank_best_course("Técnico em Redes de Computadores", candidates)
    assert best is not None
    assert best.external_id == "38786021"
    assert score >= 0.95

    # Also works when user queries without the word "técnico"
    best2, score2 = rank_best_course("redes de computadores", candidates)
    assert best2 is not None
    assert best2.external_id == "38786021"
    assert score2 >= 0.85


def test_rank_best_course_returns_none_for_irrelevant_query():
    candidates = [
        CourseData(
            id="52620802",
            name="Técnico em Modelagem do Vestuário",
            slug="cursos-tecnicos/curso-tecnico-em-modelagem-do-vestuario",
            category="cursos-tecnicos",
            external_id="52620802",
        )
    ]
    best, score = rank_best_course("gastronomia e confeitaria", candidates)
    assert best is None
    assert score < 0.40


# =========================================================================
# 4: Removal of Modelagem Fallback
# =========================================================================

@pytest.mark.asyncio
async def test_fetch_technical_course_offers_raises_value_error_when_var_data_missing():
    """Verify that fetch_technical_course_offers does NOT silently fall back to Modelagem do Vestuário
    when HTML has no var data."""
    html_without_var_data = "<html><head><title>Curso Sem Turmas</title></head><body>Apenas texto</body></html>"

    scraper = SenacScraper()
    course = CourseData(
        id="38786021",
        name="Técnico em Redes de Computadores",
        slug="cursos-tecnicos/curso-tecnico-em-redes-de-computadores",
        category="cursos-tecnicos",
        external_id="38786021",
    )
    with patch.object(scraper, "fetch_page_html", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = html_without_var_data

        with pytest.raises(ValueError) as excinfo:
            await scraper.fetch_technical_course_offers(course)

        assert "var data" in str(excinfo.value)
        assert "52620802" not in str(excinfo.value)


# =========================================================================
# 5: Search Error Handling and Diagnostic Metadata
# =========================================================================

@pytest.mark.asyncio
async def test_search_courses_api_handles_network_failure():
    """Verify search_courses_api raises on network failure and provider returns SearchStatus.ERROR."""
    scraper = SenacScraper()
    with patch.object(scraper, "_request_with_retry", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(httpx.ConnectError):
            await scraper.search_courses_api("redes")

    provider = SenacSPProvider()
    with patch.object(provider.scraper, "search_courses_api", side_effect=httpx.ConnectError("Connection refused")):
        res = await provider.search_offers_structured("redes")
        assert res.status == SearchStatus.ERROR
        assert "Falha técnica" in res.message


# =========================================================================
# 6: Differentiation of Search Statuses
# =========================================================================

@pytest.mark.asyncio
async def test_structured_search_course_not_found():
    provider = SenacSPProvider()

    with patch.object(provider.scraper, "search_courses_api", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = []

        result = await provider.search_offers_structured("curso inexistente xyz 123")
        assert result.status == SearchStatus.COURSE_NOT_FOUND
        assert result.offers == []
        assert "não encontrado" in result.message.lower()


@pytest.mark.asyncio
async def test_structured_search_unsupported_course_type():
    """Graduação / Cursos Livres must return UNSUPPORTED_COURSE_TYPE with offers=[]."""
    provider = SenacSPProvider()

    mock_candidates = [
        CourseData(
            id="99999",
            name="Tecnologia em Análise e Desenvolvimento de Sistemas",
            slug="graduacao/tecnologia-em-analise-e-desenvolvimento-de-sistemas",
            category="graduacao",
            external_id="99999",
        )
    ]

    with patch.object(provider.scraper, "search_courses_api", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_candidates

        result = await provider.search_offers_structured("Análise e Desenvolvimento de Sistemas")
        assert result.status == SearchStatus.UNSUPPORTED_COURSE_TYPE
        assert result.offers == []  # MUST NOT pass fake offers to MatchingEngine
        assert "exclusivamente Cursos Técnicos" in result.message
        assert result.course_name == "Tecnologia em Análise e Desenvolvimento de Sistemas"
        assert result.category == "graduacao"


@pytest.mark.asyncio
async def test_structured_search_no_classes_found():
    provider = SenacSPProvider()

    mock_candidates = [
        CourseData(
            id="38786021",
            name="Técnico em Redes de Computadores",
            slug="cursos-tecnicos/curso-tecnico-em-redes-de-computadores",
            category="cursos-tecnicos",
            external_id="38786021",
        )
    ]

    with patch.object(provider.scraper, "search_courses_api", new_callable=AsyncMock) as mock_search, \
         patch.object(provider.scraper, "fetch_technical_course_offers", new_callable=AsyncMock) as mock_fetch:
        mock_search.return_value = mock_candidates
        mock_fetch.return_value = ({}, [])

        result = await provider.search_offers_structured("redes de computadores")
        assert result.status == SearchStatus.NO_CLASSES_FOUND
        assert result.offers == []
        assert result.classes_count == 0


@pytest.mark.asyncio
async def test_structured_search_classes_found_no_availability():
    provider = SenacSPProvider()

    mock_candidates = [
        CourseData(
            id="38786021",
            name="Técnico em Redes de Computadores",
            slug="cursos-tecnicos/curso-tecnico-em-redes-de-computadores",
            category="cursos-tecnicos",
            external_id="38786021",
        )
    ]

    closed_offer = OfferState(
        curso="Técnico em Redes de Computadores",
        unidade="Senac Lapa Tito",
        turno="Noturno",
        status="Inscrições encerradas",
        inscricao_disponivel=False,
        bolsa_disponivel=False,
        codigo_oferta="turma-1",
        url="https://www.sp.senac.br/cursos-tecnicos/curso-tecnico-em-redes-de-computadores",
    )

    with patch.object(provider.scraper, "search_courses_api", new_callable=AsyncMock) as mock_search, \
         patch.object(provider.scraper, "fetch_technical_course_offers", new_callable=AsyncMock) as mock_fetch:
        mock_search.return_value = mock_candidates
        mock_fetch.return_value = ({}, [closed_offer])

        result = await provider.search_offers_structured("redes de computadores")
        assert result.status == SearchStatus.CLASSES_FOUND_NO_AVAILABILITY
        assert len(result.offers) == 1
        assert result.offers[0].inscricao_disponivel is False
        assert result.offers[0].bolsa_disponivel is False


@pytest.mark.asyncio
async def test_structured_search_available_offers_found():
    provider = SenacSPProvider()

    mock_candidates = [
        CourseData(
            id="38786021",
            name="Técnico em Redes de Computadores",
            slug="cursos-tecnicos/curso-tecnico-em-redes-de-computadores",
            category="cursos-tecnicos",
            external_id="38786021",
        )
    ]

    open_offer = OfferState(
        curso="Técnico em Redes de Computadores",
        unidade="Senac Lapa Tito",
        turno="Noturno",
        status="Inscrições abertas",
        inscricao_disponivel=True,
        bolsa_disponivel=False,
        codigo_oferta="turma-1",
        url="https://www.sp.senac.br/cursos-tecnicos/curso-tecnico-em-redes-de-computadores",
    )

    with patch.object(provider.scraper, "search_courses_api", new_callable=AsyncMock) as mock_search, \
         patch.object(provider.scraper, "fetch_technical_course_offers", new_callable=AsyncMock) as mock_fetch:
        mock_search.return_value = mock_candidates
        mock_fetch.return_value = ({}, [open_offer])

        result = await provider.search_offers_structured("redes de computadores")
        assert result.status == SearchStatus.AVAILABLE_OFFERS_FOUND
        assert len(result.offers) == 1
        assert result.offers[0].inscricao_disponivel is True


# =========================================================================
# 7 & 8: /check using MatchingEngine and Real query_text Propagation
# =========================================================================

@pytest.mark.asyncio
async def test_run_user_check_propagates_query_text_and_uses_matching_engine():
    """Verify that run_user_check:
    1. Sends monitor.query_text to provider.search_offers_structured.
    2. Runs MatchingEngine on offers with vacancies.
    3. Formats custom feedback for matched offers.
    """
    link_manager = TelegramLinkManager()
    t1 = link_manager.generate_token("user-100")
    link_manager.validate_and_consume(t1.token, "chat-100")

    repo = SupabaseMonitorRepository()
    repo.seed_in_memory_monitor(
        UserMonitor(
            id="m-42",
            user_id="user-100",
            query_text="Técnico em Redes de Computadores",
            active=True,
            shift="Noturno",
            telegram_chat_id="chat-100",
        )
    )

    matching_engine = MatchingEngine()
    db_mock = MagicMock()
    worker = CourseWorker(
        database=db_mock,
        link_manager=link_manager,
        monitor_repo=repo,
        matching_engine=matching_engine,
    )

    provider_mock = AsyncMock()
    provider_mock.name = "Senac São Paulo"
    matched_offer = NormalizedOffer(
        provider_slug="senac_sp",
        institution_name="Senac São Paulo",
        external_id="turma-101",
        title="Técnico em Redes de Computadores",
        campus_or_unit="Senac Lapa Tito",
        shift="Noturno",
        status="Inscrições abertas",
        inscricao_disponivel=True,
        bolsa_disponivel=False,
        source_url="https://www.sp.senac.br/cursos-tecnicos/redes",
    )

    provider_result = ProviderSearchResult(
        provider_slug="senac_sp",
        search_query="Técnico em Redes de Computadores",
        status=SearchStatus.AVAILABLE_OFFERS_FOUND,
        course_name="Técnico em Redes de Computadores",
        classes_count=1,
        available_classes_count=1,
        offers=[matched_offer],
    )
    provider_mock.search_offers_structured = AsyncMock(return_value=provider_result)

    worker.registry.get_active_providers = MagicMock(return_value={"senac_sp": provider_mock})

    msg = await worker.run_user_check(chat_id="chat-100")

    # Check 1: Provider received the real monitor.query_text
    provider_mock.search_offers_structured.assert_called_once_with("Técnico em Redes de Computadores")

    # Check 2: Matching engine produced a match and message includes 🎉 and course details
    assert "🎉" in msg
    assert "Técnico em Redes de Computadores" in msg
    assert "Senac Lapa Tito" in msg


@pytest.mark.asyncio
async def test_run_user_check_unsupported_course_message():
    """Verify that run_user_check returns an explanatory message for unsupported course types."""
    link_manager = TelegramLinkManager()
    t1 = link_manager.generate_token("user-100")
    link_manager.validate_and_consume(t1.token, "chat-100")

    repo = SupabaseMonitorRepository()
    repo.seed_in_memory_monitor(
        UserMonitor(
            id="m-43",
            user_id="user-100",
            query_text="Análise e Desenvolvimento de Sistemas",
            active=True,
            telegram_chat_id="chat-100",
        )
    )

    db_mock = MagicMock()
    worker = CourseWorker(
        database=db_mock,
        link_manager=link_manager,
        monitor_repo=repo,
    )

    provider_mock = AsyncMock()
    provider_mock.name = "Senac São Paulo"
    provider_result = ProviderSearchResult(
        provider_slug="senac_sp",
        search_query="Análise e Desenvolvimento de Sistemas",
        status=SearchStatus.UNSUPPORTED_COURSE_TYPE,
        course_name="Tecnologia em Análise e Desenvolvimento de Sistemas",
        category="graduacao",
        classes_count=0,
        available_classes_count=0,
        offers=[],
    )
    provider_mock.search_offers_structured = AsyncMock(return_value=provider_result)
    worker.registry.get_active_providers = MagicMock(return_value={"senac_sp": provider_mock})

    msg = await worker.run_user_check(chat_id="chat-100")
    assert "⚠️" in msg
    assert "Tecnologia em Análise e Desenvolvimento de Sistemas" in msg
    assert "graduacao" in msg
