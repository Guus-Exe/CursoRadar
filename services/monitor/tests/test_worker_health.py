"""Tests for CourseWorker execution, multi-user alerting, heartbeat and error tracking."""

from typing import List, Optional
import pytest
from app.config import Settings
from app.database import Database
from app.matching import MatchingEngine, MonitorPreferences, UserMonitor
from app.models import DiscoveredOffer, OfferState
from app.notifications.telegram import TelegramProvider
from app.providers.base import CourseData, EducationProvider, LocationData
from app.worker import CourseWorker


class MockEducationProvider(EducationProvider):
    """Mock education provider with controllable states."""

    def __init__(self, states: List[OfferState], fail: bool = False):
        self.states = list(states)
        self.fail = fail

    @property
    def institution_slug(self) -> str:
        return "senac-sp"

    @property
    def institution_name(self) -> str:
        return "Senac São Paulo"

    async def get_locations(self) -> List[LocationData]:
        return []

    async def search_courses(self, query: str) -> List[CourseData]:
        return []

    async def discover_offers(
        self, course_name: str, unit_name: str, shift: Optional[str] = None
    ) -> List[DiscoveredOffer]:
        return []

    async def get_offer_state(self, url_or_id: str) -> OfferState:
        if self.fail:
            raise ConnectionError("Mock provider failure")
        if self.states:
            return self.states.pop(0)
        return OfferState(
            curso="Técnico em Modelagem do Vestuário",
            unidade="Senac Lapa Faustolo",
            turno="Noturno",
            status="Indisponível",
        )


class MockTelegramProvider(TelegramProvider):
    """Captures sent messages."""

    def __init__(self):
        super().__init__(bot_token="fake-token")
        self.sent_messages = []

    async def send_to_user(self, recipient_id: str, text: str) -> bool:
        self.sent_messages.append((recipient_id, text))
        return True


@pytest.mark.asyncio
async def test_worker_cycle_and_heartbeat(temp_db: Database):
    """Validates worker execution cycle, matching, and heartbeat tracking."""
    state_closed = OfferState(
        curso="Técnico em Modelagem do Vestuário",
        unidade="Senac Lapa Faustolo",
        turno="Noturno",
        status="Sem vagas",
        inscricao_disponivel=False,
        bolsa_disponivel=False,
        codigo_oferta="9900357333",
    )
    # Pre-record baseline state in database
    temp_db.upsert_offer(
        offer_id="9900357333",
        curso=state_closed.curso,
        unidade=state_closed.unidade,
        turno=state_closed.turno,
        url="https://www.sp.senac.br",
        state=state_closed,
    )

    state_open = OfferState(
        curso="Técnico em Modelagem do Vestuário",
        unidade="Senac Lapa Faustolo",
        turno="Noturno",
        status="Inscrições abertas",
        inscricao_disponivel=True,
        bolsa_disponivel=False,
        codigo_oferta="9900357333",
        botoes=["Comprar curso"],
    )

    provider = MockEducationProvider(states=[state_open])
    telegram = MockTelegramProvider()
    worker = CourseWorker(
        worker_id="test-worker-alpha",
        database=temp_db,
        provider=provider,
        telegram_provider=telegram,
    )

    # Register 2 active monitors with Telegram
    worker.register_monitor(
        UserMonitor(
            id="mon-1",
            user_id="user-1",
            institution_id="11111111-1111-1111-1111-111111111111",
            location_id="22222222-2222-2222-2222-222222222221",
            course_id="33333333-3333-3333-3333-333333333331",
            shift="Noturno",
            active=True,
            telegram_chat_id="chat-user-1",
        )
    )
    worker.register_monitor(
        UserMonitor(
            id="mon-2",
            user_id="user-2",
            institution_id="11111111-1111-1111-1111-111111111111",
            location_id="22222222-2222-2222-2222-222222222221",
            course_id="33333333-3333-3333-3333-333333333331",
            shift="Noturno",
            active=True,
            telegram_chat_id="chat-user-2",
        )
    )

    # Run check cycle
    result = await worker.run_check_cycle()
    assert result["status"] == "completed"
    assert result["offers_checked"] == 1
    assert result["offers_succeeded"] == 1

    # Check that both users were alerted
    assert len(telegram.sent_messages) == 2
    recipients = [r for r, _ in telegram.sent_messages]
    assert "chat-user-1" in recipients
    assert "chat-user-2" in recipients

    # Check heartbeat in database
    latest_health = temp_db.get_latest_worker_health(worker_id="test-worker-alpha")
    assert latest_health is not None
    assert latest_health.worker_id == "test-worker-alpha"
    assert latest_health.status == "healthy"
    assert latest_health.offers_checked == 1


@pytest.mark.asyncio
async def test_worker_error_tracking(temp_db: Database):
    """Validates that failures are logged to system_errors and degrade health."""
    provider = MockEducationProvider(states=[], fail=True)
    worker = CourseWorker(
        worker_id="test-worker-err",
        database=temp_db,
        provider=provider,
    )

    result = await worker.run_check_cycle()
    assert result["offers_failed"] == 1

    # Verify worker health is marked degraded
    health = temp_db.get_latest_worker_health(worker_id="test-worker-err")
    assert health is not None
    assert health.status == "degraded"
    assert health.offers_failed == 1
