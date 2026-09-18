"""Tests for CursoRadar multi-user worker, Supabase synchronization, and targeted alerts."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from app.config import Settings
from app.database import Database
from app.matching import MatchingEngine, MonitorPreferences, OfferChangeEvent, UserMonitor
from app.models import OfferState
from app.monitors_repo import SupabaseMonitorRepository
from app.notifications.telegram import TelegramProvider
from app.providers.base import EducationProvider, NormalizedOffer
from app.providers.registry import ProviderRegistry
from app.telegram_link import TelegramLinkManager
from app.worker import CourseWorker


class MockEducationProvider(EducationProvider):
    """Mock education provider for testing."""

    def __init__(self, slug="senac_sp", name="Senac São Paulo"):
        self._slug = slug
        self._name = name
        self.enabled = True

    @property
    def slug(self) -> str:
        return self._slug

    @property
    def name(self) -> str:
        return self._name

    @property
    def institution_slug(self) -> str:
        return "senac-sp"

    @property
    def institution_name(self) -> str:
        return self._name

    def healthcheck(self) -> bool:
        return True

    async def search_offers(self, query: str = "", **kwargs):
        return [
            NormalizedOffer(
                provider_slug=self.slug,
                external_id="ext-123",
                title=query,
                institution_name=self.name,
                modality="presencial",
                shift="Noturno",
                source_url="https://example.com/course",
                status="Disponível",
            )
        ]

    async def get_locations(self):
        return []

    async def search_courses(self, query: str):
        return []

    async def discover_offers(self, course_name: str, unit_name: str, shift=None):
        return []

    async def get_offer_state(self, url_or_id: str) -> OfferState:
        return OfferState(
            curso="Administração do Ubuntu Server",
            unidade="Senac Lapa Tito",
            turno="Noturno",
            status="Inscrições abertas",
            codigo_oferta="ubuntu-101",
            inscricao_disponivel=True,
            bolsa_disponivel=False,
        )


# ---------------------------------------------------------------------------
# TEST 1: Carregar monitors do Supabase
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_load_monitors_from_supabase():
    """Validates loading monitors from Supabase and mapping them to domain UserMonitor models."""
    mock_supabase = MagicMock()
    select_mock = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value = select_mock
    select_mock.execute.return_value = MagicMock(
        data=[
            {
                "id": "10dff106-ee9d-401c-b4b4-8da27aaec484",
                "user_id": "8023f997-920d-47fe-82ca-05b9c715cafb",
                "query_text": "Administração do Ubuntu Server",
                "active": True,
                "shift": None,
                "city": "São Paulo",
                "state": "SP",
                "modality": "all",
                "opportunity_type": "all",
                "all_providers": True,
                "notify_channels": ["dashboard", "telegram"],
            }
        ]
    )

    repo = SupabaseMonitorRepository(supabase_client=mock_supabase)
    monitors = await repo.list_active_monitors()

    assert len(monitors) == 1
    mon = monitors[0]
    assert mon.id == "10dff106-ee9d-401c-b4b4-8da27aaec484"
    assert mon.user_id == "8023f997-920d-47fe-82ca-05b9c715cafb"
    assert mon.query_text == "Administração do Ubuntu Server"
    assert mon.active is True
    assert mon.all_providers is True


# ---------------------------------------------------------------------------
# TEST 2: Somente active=true
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_only_active_monitors_loaded():
    """Ensures that repository queries specifically filter by active = True."""
    mock_supabase = MagicMock()
    repo = SupabaseMonitorRepository(supabase_client=mock_supabase)

    await repo.list_active_monitors()

    mock_supabase.table.assert_called_with("monitors")
    mock_supabase.table().select.assert_called_with("*")
    mock_supabase.table().select().eq.assert_called_with("active", True)


# ---------------------------------------------------------------------------
# TEST 3: Isolamento entre user_id
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_user_id_isolation():
    """Validates that get_user_monitors returns only monitors belonging to that user."""
    repo = SupabaseMonitorRepository()
    m1 = UserMonitor(id="m-1", user_id="user-gustavo", query_text="Ubuntu Server", active=True)
    m2 = UserMonitor(id="m-2", user_id="user-outro", query_text="Python Avançado", active=True)
    repo.seed_in_memory_monitor(m1)
    repo.seed_in_memory_monitor(m2)

    gustavo_monitors = await repo.get_user_monitors("user-gustavo")
    assert len(gustavo_monitors) == 1
    assert gustavo_monitors[0].id == "m-1"
    assert gustavo_monitors[0].query_text == "Ubuntu Server"


# ---------------------------------------------------------------------------
# TEST 4: chat_id resolve usuário correto
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chat_id_resolves_correct_user(temp_db: Database):
    """Validates that chat_id correctly resolves to user_id and hydates telegram_chat_id."""
    link_manager = TelegramLinkManager()
    token = link_manager.generate_token("user-gustavo")
    link_manager.validate_and_consume(token.token, "6118615306")

    repo = SupabaseMonitorRepository()
    m = UserMonitor(id="m-1", user_id="user-gustavo", query_text="Ubuntu Server", active=True)
    repo.seed_in_memory_monitor(m)

    worker = CourseWorker(
        database=temp_db,
        link_manager=link_manager,
        monitor_repo=repo,
    )

    synced = await worker.sync_monitors_from_supabase()
    assert len(synced) == 1
    assert synced[0].telegram_chat_id == "6118615306"


# ---------------------------------------------------------------------------
# TEST 5: /status não mostra monitor de outro usuário
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_status_command_user_isolation(temp_db: Database):
    """Validates that /status strictly displays only the requesting user's monitors."""
    link_manager = TelegramLinkManager()
    t1 = link_manager.generate_token("user-gustavo")
    link_manager.validate_and_consume(t1.token, "chat-gustavo")

    t2 = link_manager.generate_token("user-outro")
    link_manager.validate_and_consume(t2.token, "chat-outro")

    repo = SupabaseMonitorRepository()
    repo.seed_in_memory_monitor(
        UserMonitor(id="m-g", user_id="user-gustavo", query_text="Administração do Ubuntu Server", active=True)
    )
    repo.seed_in_memory_monitor(
        UserMonitor(id="m-o", user_id="user-outro", query_text="Técnico em Enfermagem", active=True)
    )

    worker = CourseWorker(
        database=temp_db,
        link_manager=link_manager,
        monitor_repo=repo,
    )

    gustavo_status = await worker.get_status_summary(chat_id="chat-gustavo")
    assert "Administração do Ubuntu Server" in gustavo_status
    assert "Técnico em Enfermagem" not in gustavo_status

    outro_status = await worker.get_status_summary(chat_id="chat-outro")
    assert "Técnico em Enfermagem" in outro_status
    assert "Administração do Ubuntu Server" not in outro_status


# ---------------------------------------------------------------------------
# TEST 6: /check só verifica monitors do usuário
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_check_command_user_monitors(temp_db: Database):
    """Validates that /check runs checks only for the user's active monitors."""
    link_manager = TelegramLinkManager()
    t1 = link_manager.generate_token("user-gustavo")
    link_manager.validate_and_consume(t1.token, "chat-gustavo")

    repo = SupabaseMonitorRepository()
    repo.seed_in_memory_monitor(
        UserMonitor(id="m-g", user_id="user-gustavo", query_text="Administração do Ubuntu Server", active=True)
    )
    repo.seed_in_memory_monitor(
        UserMonitor(id="m-o", user_id="user-outro", query_text="Design de Interiores", active=True)
    )

    worker = CourseWorker(
        database=temp_db,
        link_manager=link_manager,
        monitor_repo=repo,
    )

    res = await worker.run_user_check(chat_id="chat-gustavo")
    assert "Administração do Ubuntu Server" in res
    assert "Design de Interiores" not in res


# ---------------------------------------------------------------------------
# TEST 7: /pause altera apenas monitor daquele usuário
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pause_command_alters_only_user_monitors(temp_db: Database):
    """Validates that /pause pauses only the specified user monitor, preserving other users and global worker."""
    link_manager = TelegramLinkManager()
    t1 = link_manager.generate_token("user-gustavo")
    link_manager.validate_and_consume(t1.token, "chat-gustavo")

    repo = SupabaseMonitorRepository()
    m_gustavo = UserMonitor(id="m-g", user_id="user-gustavo", query_text="Ubuntu Server", active=True)
    m_outro = UserMonitor(id="m-o", user_id="user-outro", query_text="Python", active=True)
    repo.seed_in_memory_monitor(m_gustavo)
    repo.seed_in_memory_monitor(m_outro)

    worker = CourseWorker(
        database=temp_db,
        link_manager=link_manager,
        monitor_repo=repo,
    )
    await worker.sync_monitors_from_supabase()

    res = await worker.pause_user(chat_id="chat-gustavo", arg="1")
    assert "pausado com sucesso" in res

    # Gustavos monitor is paused
    assert m_gustavo.active is False
    # Other user's monitor remains active
    assert m_outro.active is True
    # Global worker is NOT paused
    assert worker.is_paused is False


# ---------------------------------------------------------------------------
# TEST 8: /resume altera apenas monitor daquele usuário
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_resume_command_alters_only_user_monitors(temp_db: Database):
    """Validates that /resume resumes only the user's paused monitor."""
    link_manager = TelegramLinkManager()
    t1 = link_manager.generate_token("user-gustavo")
    link_manager.validate_and_consume(t1.token, "chat-gustavo")

    repo = SupabaseMonitorRepository()
    m_gustavo = UserMonitor(id="m-g", user_id="user-gustavo", query_text="Ubuntu Server", active=False)
    repo.seed_in_memory_monitor(m_gustavo)

    worker = CourseWorker(
        database=temp_db,
        link_manager=link_manager,
        monitor_repo=repo,
    )
    await worker.sync_monitors_from_supabase()

    res = await worker.resume_user(chat_id="chat-gustavo", arg="1")
    assert "reativado com sucesso" in res
    assert m_gustavo.active is True


# ---------------------------------------------------------------------------
# TEST 9: Matching preserva monitor_id e user_id
# ---------------------------------------------------------------------------
def test_matching_preserves_monitor_and_user_id():
    """Validates that MatchingEngine preserves user_id and monitor_id on MatchResult."""
    matching = MatchingEngine()
    mon = UserMonitor(
        id="mon-uuid-1234",
        user_id="user-uuid-5678",
        query_text="Ubuntu Server",
        active=True,
        telegram_chat_id="chat-111",
        all_providers=True,
    )

    state = OfferState(
        curso="Administração do Ubuntu Server",
        unidade="Lapa Tito",
        turno="Noturno",
        status="Inscrições abertas",
        codigo_oferta="off-1",
        inscricao_disponivel=True,
        bolsa_disponivel=False,
    )

    event = OfferChangeEvent(
        offer_id="off-1",
        provider_slug="senac_sp",
        institution_name="Senac São Paulo",
        change_type="STATUS_CHANGE",
        current_state=state,
        title="Administração do Ubuntu Server",
    )

    matches = matching.match(event, [mon])
    assert len(matches) == 1
    match = matches[0]
    assert match.monitor_id == "mon-uuid-1234"
    assert match.user_id == "user-uuid-5678"
    assert match.telegram_chat_id == "chat-111"


# ---------------------------------------------------------------------------
# TEST 10: Alerta vai apenas para telegram_chat_id correto
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_alert_dispatched_only_to_target_chat_id(temp_db: Database):
    """Validates that alert dispatch targets strictly the monitor owner's telegram_chat_id."""
    mock_telegram = MagicMock()
    mock_telegram.send_to_user = AsyncMock(return_value=True)

    # Pre-record baseline closed state in database
    state_closed = OfferState(
        curso="Administração do Ubuntu Server",
        unidade="Senac Lapa Tito",
        turno="Noturno",
        status="Sem vagas",
        codigo_oferta="9900357333",
        inscricao_disponivel=False,
        bolsa_disponivel=False,
    )
    temp_db.upsert_offer(
        offer_id="9900357333",
        curso=state_closed.curso,
        unidade=state_closed.unidade,
        turno=state_closed.turno,
        url="https://www.sp.senac.br",
        state=state_closed,
    )

    provider = MockEducationProvider()
    worker = CourseWorker(
        database=temp_db,
        provider=provider,
        telegram_provider=mock_telegram,
    )

    mon1 = UserMonitor(
        id="mon-1",
        user_id="user-1",
        query_text="Ubuntu Server",
        active=True,
        telegram_chat_id="chat-target-user-1",
        all_providers=True,
    )
    mon2 = UserMonitor(
        id="mon-2",
        user_id="user-2",
        query_text="Gastronomia",
        active=True,
        telegram_chat_id="chat-other-user-2",
        all_providers=True,
    )

    worker.register_monitor(mon1)
    worker.register_monitor(mon2)

    # Trigger check cycle where mock provider returns Ubuntu open state
    await worker.run_check_cycle()

    # Verify send_to_user was called for chat-target-user-1 and NOT chat-other-user-2
    assert mock_telegram.send_to_user.call_count == 1
    call_kwargs = mock_telegram.send_to_user.call_args[1]
    assert call_kwargs.get("recipient_id") == "chat-target-user-1"


# ---------------------------------------------------------------------------
# TEST 11: Dois usuários com mesmo interesse recebem alertas independentes
# ---------------------------------------------------------------------------
def test_two_users_same_course_independent_alerts():
    """Validates that two users monitoring the same course receive distinct alerts with distinct fingerprints."""
    matching = MatchingEngine()
    mon1 = UserMonitor(
        id="mon-1",
        user_id="user-gustavo",
        query_text="Ubuntu Server",
        active=True,
        telegram_chat_id="chat-gustavo",
        all_providers=True,
    )
    mon2 = UserMonitor(
        id="mon-2",
        user_id="user-maria",
        query_text="Ubuntu Server",
        active=True,
        telegram_chat_id="chat-maria",
        all_providers=True,
    )

    state = OfferState(
        curso="Administração do Ubuntu Server",
        unidade="Lapa Tito",
        turno="Noturno",
        status="Inscrições abertas",
        codigo_oferta="off-ubuntu",
        inscricao_disponivel=True,
        bolsa_disponivel=False,
    )
    event = OfferChangeEvent(
        offer_id="off-ubuntu",
        provider_slug="senac_sp",
        institution_name="Senac São Paulo",
        change_type="ENROLLMENT_OPEN",
        current_state=state,
        title="Administração do Ubuntu Server",
    )

    matches = matching.match(event, [mon1, mon2])
    assert len(matches) == 2
    recipients = {m.telegram_chat_id for m in matches}
    assert recipients == {"chat-gustavo", "chat-maria"}

    # Fingerprints must be independent to prevent accidental deduplication collisions
    assert matches[0].fingerprint != matches[1].fingerprint


# ---------------------------------------------------------------------------
# TEST 12: Monitor inativo não gera alerta
# ---------------------------------------------------------------------------
def test_inactive_monitor_produces_no_alerts():
    """Validates that an inactive monitor (active = False) produces zero matches and zero alerts."""
    matching = MatchingEngine()
    inactive_mon = UserMonitor(
        id="mon-inactive",
        user_id="user-gustavo",
        query_text="Ubuntu Server",
        active=False,
        telegram_chat_id="chat-gustavo",
        all_providers=True,
    )

    state = OfferState(
        curso="Administração do Ubuntu Server",
        unidade="Lapa Tito",
        turno="Noturno",
        status="Inscrições abertas",
        codigo_oferta="off-ubuntu",
        inscricao_disponivel=True,
        bolsa_disponivel=False,
    )
    event = OfferChangeEvent(
        offer_id="off-ubuntu",
        provider_slug="senac_sp",
        institution_name="Senac São Paulo",
        change_type="STATUS_CHANGE",
        current_state=state,
        title="Administração do Ubuntu Server",
    )

    matches = matching.match(event, [inactive_mon])
    assert len(matches) == 0


# ---------------------------------------------------------------------------
# TEST 13: Supabase indisponível não derruba worker (last-known-good)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_supabase_unavailability_resilience(temp_db: Database):
    """Validates that if Supabase fails, the worker logs the error, retains last-known-good cache, and keeps running."""
    mock_supabase = MagicMock()
    mock_supabase.table.side_effect = RuntimeError("Supabase connection timeout / network down")

    repo = SupabaseMonitorRepository(supabase_client=mock_supabase)
    worker = CourseWorker(
        database=temp_db,
        monitor_repo=repo,
    )

    # Populate last-known-good cache
    cached_mon = UserMonitor(id="cached-1", user_id="u-1", query_text="Ubuntu", active=True)
    worker.active_monitors = [cached_mon]

    # Attempt synchronization while Supabase is down
    result = await worker.sync_monitors_from_supabase()

    # Must retain last-known-good cache and not crash
    assert len(result) == 1
    assert result[0].id == "cached-1"
    assert worker.active_monitors == [cached_mon]


# ---------------------------------------------------------------------------
# TEST 14: CourseMonitor legado não domina o fluxo quando existem monitors no Supabase
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_legacy_course_monitor_not_dominating(temp_db: Database):
    """Validates that CourseWorker is the primary runner and does not perform broadcast of legacy offer."""
    settings = Settings(enable_legacy_monitor=False)
    repo = SupabaseMonitorRepository()
    repo.seed_in_memory_monitor(
        UserMonitor(id="mon-ubuntu", user_id="user-gustavo", query_text="Administração do Ubuntu Server", active=True)
    )

    mock_telegram = MagicMock()
    mock_telegram.send_to_user = AsyncMock(return_value=True)

    worker = CourseWorker(
        settings=settings,
        database=temp_db,
        monitor_repo=repo,
        telegram_provider=mock_telegram,
    )

    await worker.sync_monitors_from_supabase()
    assert len(worker.active_monitors) == 1
    assert worker.active_monitors[0].query_text == "Administração do Ubuntu Server"
    assert settings.enable_legacy_monitor is False
