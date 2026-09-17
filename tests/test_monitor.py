"""Tests for CourseMonitor orchestration, alerting, and error recovery."""

from typing import List, Optional
import pytest
from app.config import Settings
from app.database import Database
from app.models import DiscoveredOffer, OfferState, StateDiff
from app.monitor import CourseMonitor
from app.notifications.base import NotificationProvider
from app.scrapers.base import BaseScraper


class MockScraper(BaseScraper):
    """Mock scraper to simulate changing offer states and network failures."""

    def __init__(self, states: List[OfferState], fail_count: int = 0):
        self.states = list(states)
        self.fail_count = fail_count
        self.call_count = 0
        self.discovered_offers: List[DiscoveredOffer] = []

    async def get_offer_state(self, url_or_id: str) -> OfferState:
        self.call_count += 1
        if self.fail_count > 0:
            self.fail_count -= 1
            raise ConnectionError("Mock connection failure")
        if self.states:
            return self.states.pop(0)
        return OfferState(
            curso="Técnico em Modelagem do Vestuário",
            unidade="Senac Lapa Faustolo",
            turno="Noturno",
            status="Sem vagas disponíveis",
        )

    async def discover_new_offers(
        self, course_name: str, unit_name: str, shift: Optional[str] = None
    ) -> List[DiscoveredOffer]:
        return self.discovered_offers


class MockNotificationProvider(NotificationProvider):
    """Captures sent alerts for assertions."""

    def __init__(self):
        self.offer_alerts: List[StateDiff] = []
        self.new_offer_alerts: List[DiscoveredOffer] = []
        self.health_alerts: List[int] = []
        self.messages: List[str] = []

    async def send_offer_alert(self, diff: StateDiff, url: str) -> bool:
        self.offer_alerts.append(diff)
        return True

    async def send_new_offer_alert(self, offer: DiscoveredOffer) -> bool:
        self.new_offer_alerts.append(offer)
        return True

    async def send_health_alert(self, consecutive_failures: int, details: Optional[str] = None) -> bool:
        self.health_alerts.append(consecutive_failures)
        return True

    async def send_message(self, text: str) -> bool:
        self.messages.append(text)
        return True


@pytest.mark.asyncio
async def test_monitor_full_flow(temp_db: Database):
    """Tests baseline registration -> opportunity alert -> duplicate prevention."""
    settings = Settings(
        DATABASE_URL=f"sqlite:///{temp_db.engine.url.database}",
        CONSECUTIVE_FAILURES_ALERT_THRESHOLD=3,
    )

    state_closed = OfferState(
        curso="Técnico em Modelagem do Vestuário",
        unidade="Senac Lapa Faustolo",
        turno="Noturno",
        status="Sem vagas disponíveis",
        bolsa_disponivel=False,
        inscricao_disponivel=False,
        codigo_oferta="9900357333",
    )

    state_opened = state_closed.model_copy(
        update={
            "status": "Inscrições abertas",
            "inscricao_disponivel": True,
            "bolsa_disponivel": True,
            "botoes": ["Comprar curso", "Bolsa de estudo"],
        }
    )

    # Scraper sequence: 1. closed (baseline), 2. opened (opportunity), 3. still opened (prevent duplicate)
    scraper = MockScraper(states=[state_closed, state_opened, state_opened])
    provider = MockNotificationProvider()

    monitor = CourseMonitor(
        settings=settings,
        database=temp_db,
        scraper=scraper,
        providers=[provider],
    )

    # Step 1: Baseline run
    diff1 = await monitor.run_check_cycle()
    assert diff1 is not None
    assert not diff1.has_changed
    assert len(provider.offer_alerts) == 0  # No alert on baseline

    # Step 2: Opportunity arises
    diff2 = await monitor.run_check_cycle()
    assert diff2 is not None
    assert diff2.has_changed is True
    assert diff2.is_actionable is True
    assert len(provider.offer_alerts) == 1  # Alert sent!
    assert diff2.current_state.inscricao_disponivel is True

    # Step 3: Next check still open -> Must NOT duplicate alert
    diff3 = await monitor.run_check_cycle()
    assert diff3 is not None
    assert len(provider.offer_alerts) == 1  # Still 1, duplicate prevented!


@pytest.mark.asyncio
async def test_monitor_health_alert_and_recovery(temp_db: Database):
    """Tests consecutive failures threshold alerting and recovery notice."""
    settings = Settings(
        DATABASE_URL=f"sqlite:///{temp_db.engine.url.database}",
        CONSECUTIVE_FAILURES_ALERT_THRESHOLD=3,
    )

    # Scraper that fails 3 times, then succeeds
    state_ok = OfferState(
        curso="Técnico em Modelagem do Vestuário",
        unidade="Senac Lapa Faustolo",
        turno="Noturno",
        status="Sem vagas",
        codigo_oferta="9900357333",
    )
    scraper = MockScraper(states=[state_ok], fail_count=3)
    provider = MockNotificationProvider()

    monitor = CourseMonitor(
        settings=settings,
        database=temp_db,
        scraper=scraper,
        providers=[provider],
    )

    # Run 1: Failure 1
    await monitor.run_check_cycle()
    assert monitor.consecutive_failures == 1
    assert len(provider.health_alerts) == 0

    # Run 2: Failure 2
    await monitor.run_check_cycle()
    assert monitor.consecutive_failures == 2
    assert len(provider.health_alerts) == 0

    # Run 3: Failure 3 -> Threshold reached!
    await monitor.run_check_cycle()
    assert monitor.consecutive_failures == 3
    assert len(provider.health_alerts) == 1  # Health alert dispatched!

    # Run 4: Success -> Recovery notice
    await monitor.run_check_cycle()
    assert monitor.consecutive_failures == 0
    assert any("restabelecida" in msg for msg in provider.messages)


@pytest.mark.asyncio
async def test_monitor_discovery(temp_db: Database):
    """Tests discovering and alerting a new offer."""
    settings = Settings(
        DATABASE_URL=f"sqlite:///{temp_db.engine.url.database}",
    )
    scraper = MockScraper(states=[])
    new_offer = DiscoveredOffer(
        codigo_oferta="9900999999",
        curso="Técnico em Modelagem do Vestuário",
        unidade="Senac Lapa Faustolo",
        turno="Noturno",
        url="https://www.sp.senac.br/nova-oferta",
    )
    scraper.discovered_offers = [new_offer]
    provider = MockNotificationProvider()

    monitor = CourseMonitor(
        settings=settings,
        database=temp_db,
        scraper=scraper,
        providers=[provider],
    )

    # Run discovery
    found = await monitor.run_discovery_cycle()
    assert len(found) == 1
    assert len(provider.new_offer_alerts) == 1
    assert provider.new_offer_alerts[0].codigo_oferta == "9900999999"

    # Running discovery again should not send duplicate
    await monitor.run_discovery_cycle()
    assert len(provider.new_offer_alerts) == 1
