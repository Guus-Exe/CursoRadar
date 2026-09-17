"""Comprehensive test suite for Multi-Provider Architecture, Registry, Matching and Deduplication."""

from typing import List, Optional, Union
import pytest
from app.database import Database
from app.matching import MatchingEngine, MonitorPreferences, OfferChangeEvent, UserMonitor
from app.models import DiscoveredOffer, OfferState
from app.notifications.telegram import TelegramProvider
from app.providers.base import CourseData, EducationProvider, LocationData, NormalizedOffer
from app.providers.registry import ProviderRegistry
from app.providers.senac import SenacSPProvider
from app.worker import CourseWorker


class DummyProvider(EducationProvider):
    """Custom provider for testing registry and multi-provider flows."""

    def __init__(
        self,
        slug_name: str,
        display_name: str,
        enabled: bool = True,
        fail: bool = False,
        state: Optional[OfferState] = None,
    ):
        self._slug = slug_name
        self._name = display_name
        self.enabled = enabled
        self.fail = fail
        self._state = state or OfferState(
            curso="Desenvolvimento de Sistemas",
            unidade="Unidade Central",
            turno="Noturno",
            status="Inscrições abertas",
            inscricao_disponivel=True,
        )

    @property
    def slug(self) -> str:
        return self._slug

    @property
    def name(self) -> str:
        return self._name

    def healthcheck(self) -> bool:
        return True

    async def search_offers(self, query: str = "", **kwargs) -> List[NormalizedOffer]:
        return [
            NormalizedOffer(
                provider_slug=self.slug,
                external_id="ext-dummy-1",
                title="Desenvolvimento Web",
                institution_name=self.name,
                source_url="https://dummy.edu.br/1",
                status="Disponível",
            )
        ]

    async def get_offer_state(self, url_or_id: str) -> Union[OfferState, NormalizedOffer]:
        if self.fail:
            raise RuntimeError(f"Provider {self.slug} connection failure!")
        return self._state


class CapturingTelegramProvider(TelegramProvider):
    """Captures sent messages for assertions."""

    def __init__(self):
        super().__init__(bot_token="fake-token")
        self.sent_messages = []

    async def send_to_user(self, recipient_id: str, text: str) -> bool:
        self.sent_messages.append((recipient_id, text))
        return True


# ---------------------------------------------------------------------------
# TEST 1: Monitor com all_providers
# ---------------------------------------------------------------------------
def test_1_monitor_all_providers():
    """Monitor with all_providers=True accepts events from any enabled provider."""
    registry = ProviderRegistry()
    p1 = DummyProvider(slug_name="senac_sp", display_name="Senac São Paulo")
    p2 = DummyProvider(slug_name="senai_sp", display_name="SENAI São Paulo")
    registry.register(p1)
    registry.register(p2)

    engine = MatchingEngine(registry=registry)

    monitor = UserMonitor(
        id="mon-all",
        user_id="user-1",
        all_providers=True,
        active=True,
        telegram_chat_id="chat-1",
        query_text="Desenvolvimento",
    )

    event_senac = OfferChangeEvent(
        offer_id="off-senac-1",
        provider_slug="senac_sp",
        institution_name="Senac São Paulo",
        title="Desenvolvimento de Jogos",
        current_state=OfferState(curso="Desenvolvimento de Jogos", status="Aberta", inscricao_disponivel=True),
        url="https://senac.br/jogos",
    )

    event_senai = OfferChangeEvent(
        offer_id="off-senai-1",
        provider_slug="senai_sp",
        institution_name="SENAI São Paulo",
        title="Desenvolvimento Web Fullstack",
        current_state=OfferState(curso="Desenvolvimento Web Fullstack", status="Aberta", inscricao_disponivel=True),
        url="https://senai.br/web",
    )

    results_senac = engine.match(event_senac, [monitor])
    assert len(results_senac) == 1
    assert results_senac[0].user_id == "user-1"
    assert "SENAC SÃO PAULO" in results_senac[0].message

    results_senai = engine.match(event_senai, [monitor])
    assert len(results_senai) == 1
    assert results_senai[0].user_id == "user-1"
    assert "SENAI SÃO PAULO" in results_senai[0].message


# ---------------------------------------------------------------------------
# TEST 2: Monitor com provider específico
# ---------------------------------------------------------------------------
def test_2_monitor_specific_provider():
    """Monitor with specific provider_slugs only accepts events from those providers."""
    registry = ProviderRegistry()
    registry.register(DummyProvider(slug_name="senac_sp", display_name="Senac São Paulo"))
    registry.register(DummyProvider(slug_name="cps_etec", display_name="Centro Paula Souza ETEC"))

    engine = MatchingEngine(registry=registry)

    mon_senac_only = UserMonitor(
        id="mon-senac",
        user_id="user-senac",
        provider_slugs=["senac_sp"],
        active=True,
        telegram_chat_id="chat-senac",
        query_text="Informática",
    )

    event_etec = OfferChangeEvent(
        offer_id="off-etec-1",
        provider_slug="cps_etec",
        institution_name="Centro Paula Souza ETEC",
        title="Técnico em Informática",
        current_state=OfferState(curso="Técnico em Informática", status="Aberta", inscricao_disponivel=True),
        url="https://etec.sp.gov.br",
    )

    event_senac = OfferChangeEvent(
        offer_id="off-senac-2",
        provider_slug="senac_sp",
        institution_name="Senac São Paulo",
        title="Técnico em Informática",
        current_state=OfferState(curso="Técnico em Informática", status="Aberta", inscricao_disponivel=True),
        url="https://senac.br/ti",
    )

    # Etec event should NOT match senac-only monitor
    assert len(engine.match(event_etec, [mon_senac_only])) == 0

    # Senac event SHOULD match
    matches = engine.match(event_senac, [mon_senac_only])
    assert len(matches) == 1
    assert matches[0].user_id == "user-senac"


# ---------------------------------------------------------------------------
# TEST 3: Provider desabilitado (não gera match/alerta)
# ---------------------------------------------------------------------------
def test_3_disabled_provider_no_match():
    """Disabled provider in registry produces no matches even with all_providers=True."""
    registry = ProviderRegistry()
    disabled_prov = DummyProvider(slug_name="disabled_prov", display_name="Disabled School", enabled=False)
    registry.register(disabled_prov)

    engine = MatchingEngine(registry=registry)

    monitor = UserMonitor(
        id="mon-all",
        user_id="user-1",
        all_providers=True,
        active=True,
        telegram_chat_id="chat-1",
    )

    event = OfferChangeEvent(
        offer_id="off-disabled-1",
        provider_slug="disabled_prov",
        institution_name="Disabled School",
        title="Qualquer Curso",
        current_state=OfferState(curso="Qualquer Curso", status="Aberta", inscricao_disponivel=True),
        url="https://disabled.edu.br",
    )

    matches = engine.match(event, [monitor])
    assert len(matches) == 0


# ---------------------------------------------------------------------------
# TEST 4: Provider inexistente (retorna None / tratamento seguro sem exceção)
# ---------------------------------------------------------------------------
def test_4_nonexistent_provider_safe_handling():
    """Non-existent provider returns None on registry.get() and handles safely in matching."""
    registry = ProviderRegistry()
    assert registry.get("inexistente") is None
    assert registry.get("") is None

    engine = MatchingEngine(registry=registry)

    monitor = UserMonitor(
        id="mon-1",
        user_id="user-1",
        all_providers=True,
        active=True,
        telegram_chat_id="chat-1",
    )

    event = OfferChangeEvent(
        offer_id="off-unknown-1",
        provider_slug="inexistente",
        title="Curso Desconhecido",
        current_state=OfferState(curso="Curso Desconhecido", status="Aberta"),
        url="https://unknown.com",
    )

    # Must execute safely without throwing unhandled exceptions
    matches = engine.match(event, [monitor])
    assert len(matches) == 0


# ---------------------------------------------------------------------------
# TEST 5: Deduplicação por external_id
# ---------------------------------------------------------------------------
def test_5_deduplication_by_external_id():
    """Successive events with identical external_id are deduplicated."""
    registry = ProviderRegistry()
    registry.register(DummyProvider(slug_name="senac_sp", display_name="Senac SP"))
    engine = MatchingEngine(registry=registry)

    monitor = UserMonitor(
        id="mon-dedup-1",
        user_id="user-dedup",
        all_providers=True,
        active=True,
        telegram_chat_id="chat-dedup",
    )

    event1 = OfferChangeEvent(
        offer_id="internal-id-1",
        external_id="EXT-UNIQUE-12345",
        provider_slug="senac_sp",
        title="Design Gráfico",
        current_state=OfferState(curso="Design Gráfico", status="Inscrições abertas", inscricao_disponivel=True),
        url="https://senac.br/design",
    )

    event2 = OfferChangeEvent(
        offer_id="internal-id-2-different",  # Different internal id, same external_id!
        external_id="EXT-UNIQUE-12345",
        provider_slug="senac_sp",
        title="Design Gráfico",
        current_state=OfferState(curso="Design Gráfico", status="Inscrições abertas", inscricao_disponivel=True),
        url="https://senac.br/design",
    )

    # First event produces 1 alert
    matches1 = engine.match(event1, [monitor])
    assert len(matches1) == 1

    # Second event with identical external_id must be deduplicated
    matches2 = engine.match(event2, [monitor])
    assert len(matches2) == 0


# ---------------------------------------------------------------------------
# TEST 6: Deduplicação por fingerprint (quando external_id é nulo)
# ---------------------------------------------------------------------------
def test_6_deduplication_by_fingerprint_when_external_id_none():
    """When external_id is None, events are deduplicated by fingerprint hash."""
    norm_offer = NormalizedOffer(
        provider_slug="senac_sp",
        title="Gastronomia Internacional",
        institution_name="Senac SP",
        city="São Paulo",
        modality="presencial",
        shift="Noturno",
        source_url="https://senac.br/gastro",
    )
    fp = norm_offer.compute_fingerprint()
    assert fp is not None and len(fp) == 64

    registry = ProviderRegistry()
    registry.register(DummyProvider(slug_name="senac_sp", display_name="Senac SP"))
    engine = MatchingEngine(registry=registry)

    monitor = UserMonitor(
        id="mon-fp-1",
        user_id="user-fp",
        all_providers=True,
        active=True,
        telegram_chat_id="chat-fp",
    )

    event1 = OfferChangeEvent(
        offer_id="offer-fp-1",
        external_id=None,
        fingerprint=fp,
        provider_slug="senac_sp",
        title="Gastronomia Internacional",
        current_state=OfferState(curso="Gastronomia Internacional", status="Aberta", inscricao_disponivel=True),
        url="https://senac.br/gastro",
    )

    event2 = OfferChangeEvent(
        offer_id="offer-fp-2",
        external_id=None,
        fingerprint=fp,  # Identical fingerprint
        provider_slug="senac_sp",
        title="Gastronomia Internacional",
        current_state=OfferState(curso="Gastronomia Internacional", status="Aberta", inscricao_disponivel=True),
        url="https://senac.br/gastro",
    )

    matches1 = engine.match(event1, [monitor])
    assert len(matches1) == 1

    matches2 = engine.match(event2, [monitor])
    assert len(matches2) == 0


# ---------------------------------------------------------------------------
# TEST 7: Matching por texto (case-insensitive e normalização)
# ---------------------------------------------------------------------------
def test_7_matching_query_text_case_and_accent_insensitive():
    """Text matching handles casing, accents, and multi-word queries."""
    registry = ProviderRegistry()
    registry.register(DummyProvider(slug_name="senac_sp", display_name="Senac SP"))
    engine = MatchingEngine(registry=registry)

    # Query with no accents and lowercase
    monitor = UserMonitor(
        id="mon-txt",
        user_id="user-txt",
        all_providers=True,
        query_text="tecnico programacao python",
        active=True,
        telegram_chat_id="chat-txt",
    )

    # Event with title containing accents and mixed case
    event = OfferChangeEvent(
        offer_id="off-txt-1",
        provider_slug="senac_sp",
        title="TÉCNICO em PROGRAMAÇÃO e Automação com Python",
        current_state=OfferState(curso="TÉCNICO em PROGRAMAÇÃO e Automação com Python", status="Aberta", inscricao_disponivel=True),
        url="https://senac.br/python",
    )

    matches = engine.match(event, [monitor])
    assert len(matches) == 1
    assert matches[0].user_id == "user-txt"


# ---------------------------------------------------------------------------
# TEST 8: Matching por cidade (presencial)
# ---------------------------------------------------------------------------
def test_8_matching_city_presential():
    """Presential courses filter matching by city."""
    registry = ProviderRegistry()
    registry.register(DummyProvider(slug_name="senac_sp", display_name="Senac SP"))
    engine = MatchingEngine(registry=registry)

    mon_sp = UserMonitor(
        id="mon-sp",
        user_id="user-sp",
        all_providers=True,
        city="São Paulo",
        active=True,
        telegram_chat_id="chat-sp",
    )
    mon_campinas = UserMonitor(
        id="mon-campinas",
        user_id="user-campinas",
        all_providers=True,
        city="Campinas",
        active=True,
        telegram_chat_id="chat-campinas",
    )

    event_sp = OfferChangeEvent(
        offer_id="off-sp",
        provider_slug="senac_sp",
        city="São Paulo",
        modality="presencial",
        title="Administração",
        current_state=OfferState(curso="Administração", unidade="Senac Tiradentes", status="Aberta", inscricao_disponivel=True),
        url="https://senac.br/sp",
    )

    matches = engine.match(event_sp, [mon_sp, mon_campinas])
    assert len(matches) == 1
    assert matches[0].user_id == "user-sp"


# ---------------------------------------------------------------------------
# TEST 9: Matching online sem cidade
# ---------------------------------------------------------------------------
def test_9_matching_online_ignores_city():
    """Online courses match regardless of monitor's city specification."""
    registry = ProviderRegistry()
    registry.register(DummyProvider(slug_name="senac_sp", display_name="Senac SP"))
    engine = MatchingEngine(registry=registry)

    mon_campinas = UserMonitor(
        id="mon-campinas",
        user_id="user-campinas",
        all_providers=True,
        city="Campinas",  # Specific city
        active=True,
        telegram_chat_id="chat-campinas",
    )

    event_online = OfferChangeEvent(
        offer_id="off-online-1",
        provider_slug="senac_sp",
        city=None,  # No city for online
        modality="online",
        title="Marketing Digital EAD",
        current_state=OfferState(curso="Marketing Digital EAD", unidade="Senac EAD", status="Aberta", inscricao_disponivel=True),
        url="https://senac.br/ead",
    )

    matches = engine.match(event_online, [mon_campinas])
    assert len(matches) == 1
    assert matches[0].user_id == "user-campinas"


# ---------------------------------------------------------------------------
# TEST 10: Matching por modalidade
# ---------------------------------------------------------------------------
def test_10_matching_modality_filtering():
    """Monitors with modality filter only match courses of the specified modality."""
    registry = ProviderRegistry()
    registry.register(DummyProvider(slug_name="senac_sp", display_name="Senac SP"))
    engine = MatchingEngine(registry=registry)

    mon_all = UserMonitor(id="mon-all", user_id="user-all", modality="all", all_providers=True, active=True, telegram_chat_id="chat-1")
    mon_presential = UserMonitor(id="mon-pres", user_id="user-pres", modality="presencial", all_providers=True, active=True, telegram_chat_id="chat-2")
    mon_online = UserMonitor(id="mon-on", user_id="user-on", modality="online", all_providers=True, active=True, telegram_chat_id="chat-3")

    event_online = OfferChangeEvent(
        offer_id="off-on-10",
        provider_slug="senac_sp",
        modality="online",
        title="Ciência de Dados",
        current_state=OfferState(curso="Ciência de Dados", status="Aberta", inscricao_disponivel=True),
        url="https://senac.br/dados",
    )

    matches = engine.match(event_online, [mon_all, mon_presential, mon_online])
    recipients = [m.user_id for m in matches]
    assert "user-all" in recipients
    assert "user-on" in recipients
    assert "user-pres" not in recipients


# ---------------------------------------------------------------------------
# TEST 11: Matching por tipo de oportunidade (bolsa, gratuito, pago)
# ---------------------------------------------------------------------------
def test_11_matching_opportunity_type():
    """Tests opportunity_type filters: bolsa, gratuito, and pago."""
    registry = ProviderRegistry()
    registry.register(DummyProvider(slug_name="senac_sp", display_name="Senac SP"))
    engine = MatchingEngine(registry=registry)

    mon_bolsa = UserMonitor(id="m-bolsa", user_id="u-bolsa", opportunity_type="bolsa", all_providers=True, active=True, telegram_chat_id="c-bolsa")
    mon_gratuito = UserMonitor(id="m-grat", user_id="u-grat", opportunity_type="gratuito", all_providers=True, active=True, telegram_chat_id="c-grat")
    mon_pago = UserMonitor(id="m-pago", user_id="u-pago", opportunity_type="pago", all_providers=True, active=True, telegram_chat_id="c-pago")

    # Offer with scholarship available
    event_bolsa = OfferChangeEvent(
        offer_id="off-bolsa",
        provider_slug="senac_sp",
        has_scholarship=True,
        bolsa_disponivel=True,
        inscricao_disponivel=False,
        is_free=False,
        current_state=OfferState(curso="Design", status="Bolsas abertas", bolsa_disponivel=True, inscricao_disponivel=False),
        url="https://senac.br/bolsa",
    )
    m1 = engine.match(event_bolsa, [mon_bolsa, mon_gratuito, mon_pago])
    assert len(m1) == 1
    assert m1[0].user_id == "u-bolsa"

    # Offer completely free (100% gratuito)
    event_free = OfferChangeEvent(
        offer_id="off-free",
        provider_slug="senac_sp",
        is_free=True,
        inscricao_disponivel=False,
        current_state=OfferState(curso="Cidadania", status="Gratuito", inscricao_disponivel=False),
        url="https://senac.br/free",
    )
    m2 = engine.match(event_free, [mon_bolsa, mon_gratuito, mon_pago])
    assert len(m2) == 1
    assert m2[0].user_id == "u-grat"

    # Offer paid with open enrollment
    event_paid = OfferChangeEvent(
        offer_id="off-paid",
        provider_slug="senac_sp",
        is_free=False,
        has_scholarship=False,
        bolsa_disponivel=False,
        inscricao_disponivel=True,
        current_state=OfferState(curso="MBA", status="Vagas abertas", inscricao_disponivel=True),
        url="https://senac.br/mba",
    )
    m3 = engine.match(event_paid, [mon_bolsa, mon_gratuito, mon_pago])
    assert len(m3) == 1
    assert m3[0].user_id == "u-pago"


# ---------------------------------------------------------------------------
# TEST 12: Isolamento entre usuários
# ---------------------------------------------------------------------------
def test_12_user_isolation():
    """User A does not receive notifications from User B's monitor, ensuring strict tenancy isolation."""
    registry = ProviderRegistry()
    registry.register(DummyProvider(slug_name="senac_sp", display_name="Senac SP"))
    engine = MatchingEngine(registry=registry)

    mon_user_a = UserMonitor(
        id="mon-a",
        user_id="user-a",
        all_providers=True,
        query_text="Enfermagem",
        active=True,
        telegram_chat_id="chat-a",
    )
    mon_user_b = UserMonitor(
        id="mon-b",
        user_id="user-b",
        all_providers=True,
        query_text="Gastronomia",
        active=True,
        telegram_chat_id="chat-b",
    )

    event_enfermagem = OfferChangeEvent(
        offer_id="off-enf-1",
        provider_slug="senac_sp",
        title="Técnico em Enfermagem",
        current_state=OfferState(curso="Técnico em Enfermagem", status="Aberta", inscricao_disponivel=True),
        url="https://senac.br/enfermagem",
    )

    matches = engine.match(event_enfermagem, [mon_user_a, mon_user_b])
    assert len(matches) == 1
    assert matches[0].user_id == "user-a"
    assert matches[0].telegram_chat_id == "chat-a"
    assert all(m.user_id != "user-b" for m in matches)


# ---------------------------------------------------------------------------
# TEST 13: Falha de um provider sem interromper outros providers no registry
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_13_worker_multi_provider_failure_resilience(temp_db: Database):
    """When one provider raises an error, the worker continues and processes remaining providers."""
    registry = ProviderRegistry()
    failing_prov = DummyProvider(slug_name="prov_fail", display_name="Failing Provider", fail=True)
    healthy_prov = DummyProvider(slug_name="prov_ok", display_name="Healthy Provider", fail=False)

    registry.register(failing_prov)
    registry.register(healthy_prov)

    telegram = CapturingTelegramProvider()
    worker = CourseWorker(
        worker_id="test-resilient-worker",
        database=temp_db,
        registry=registry,
        telegram_provider=telegram,
    )

    worker.register_monitor(
        UserMonitor(
            id="mon-resilient",
            user_id="user-resilient",
            all_providers=True,
            active=True,
            telegram_chat_id="chat-resilient",
        )
    )

    result = await worker.run_check_cycle()

    assert result["status"] == "completed"
    assert result["offers_checked"] == 2
    assert result["offers_failed"] == 1
    assert result["offers_succeeded"] == 1

    # Verify that the failing provider logged a system error
    with temp_db.get_session() as session:
        from app.database import SystemErrorModel
        from sqlalchemy import select
        err = session.execute(
            select(SystemErrorModel).where(SystemErrorModel.source.contains("prov_fail"))
        ).scalar_one_or_none()
        assert err is not None
        assert "RuntimeError" in err.error_type


# ---------------------------------------------------------------------------
# TEST 14: Persistência de alertas sem duplicação (mesmo fingerprint rejeitado)
# ---------------------------------------------------------------------------
def test_14_alert_persistence_deduplication(temp_db: Database):
    """Duplicate alert insertion with identical fingerprint is rejected by the database layer."""
    fp = "f" * 64

    # First record call succeeds
    alert1 = temp_db.record_alert(
        alert_type="VAGA_ENCONTRADA",
        offer_id="9900357333",
        state_hash=fp,
        message_content="Vaga aberta",
        channel="telegram",
        user_id="user-pers-1",
        fingerprint=fp,
    )
    assert alert1 is not None
    assert alert1.fingerprint == fp

    # Duplicate check recognizes it
    assert temp_db.is_duplicate_alert(
        alert_type="VAGA_ENCONTRADA",
        offer_id="9900357333",
        fingerprint=fp,
    ) is True

    # Second record call with same fingerprint is rejected
    alert2 = temp_db.record_alert(
        alert_type="VAGA_ENCONTRADA",
        offer_id="9900357333",
        state_hash=fp,
        message_content="Vaga aberta repetida",
        channel="telegram",
        user_id="user-pers-1",
        fingerprint=fp,
    )
    assert alert2 is None  # Rejected!


# ---------------------------------------------------------------------------
# TEST 15: Teste Senac retrocompatível
# ---------------------------------------------------------------------------
def test_15_senac_retrocompatibility():
    """Validates that legacy Senac monitors, institution properties and methods remain 100% functional."""
    senac = SenacSPProvider()
    assert senac.slug == "senac_sp"
    assert senac.name == "Senac São Paulo"
    assert senac.institution_slug == "senac-sp"
    assert senac.institution_name == "Senac São Paulo"
    assert senac.enabled is True
    assert senac.healthcheck() is True

    # Legacy monitor with UUIDs and no multi-provider fields
    legacy_mon = UserMonitor(
        id="mon-legacy",
        user_id="user-legacy",
        institution_id="11111111-1111-1111-1111-111111111111",
        location_id="22222222-2222-2222-2222-222222222221",
        course_id="33333333-3333-3333-3333-333333333331",
        shift="Noturno",
        active=True,
        telegram_chat_id="chat-legacy",
    )

    legacy_event = OfferChangeEvent(
        offer_id="9900357333",
        institution_id="11111111-1111-1111-1111-111111111111",
        location_id="22222222-2222-2222-2222-222222222221",
        course_id="33333333-3333-3333-3333-333333333331",
        shift="Noturno",
        change_type="ENROLLMENT_OPEN",
        current_state=OfferState(
            curso="Técnico em Informática",
            unidade="Senac Lapa Tito",
            turno="Noturno",
            status="Inscrições abertas",
            inscricao_disponivel=True,
        ),
        url="https://www.sp.senac.br/oferta/9900357333",
    )

    engine = MatchingEngine()
    results = engine.match(legacy_event, [legacy_mon])
    assert len(results) == 1
    assert results[0].user_id == "user-legacy"
    assert "Técnico em Informática" in results[0].message
    assert "Senac Lapa Tito" in results[0].message


# ---------------------------------------------------------------------------
# TEST 16: Alert Fingerprint - Determinismo, Sensibilidade a Entidades e Unicidade
# ---------------------------------------------------------------------------
def test_16_alert_fingerprint_deterministic_and_unique():
    """Confirms alert fingerprint is derived from user, monitor, offer, change_type, state_hash."""
    from app.matching import compute_alert_fingerprint

    # Base parameters
    u1, m1, o1, ct1, sh1 = "user-1", "mon-1", "off-1", "NEW_OFFER", "statehash123"

    fp_base = compute_alert_fingerprint(u1, m1, o1, ct1, sh1)
    assert len(fp_base) == 64
    assert fp_base != "d41d8cd98f00b204e9800998ecf8427e"  # Never empty MD5

    # 1. Same parameters must produce identical fingerprint (idempotency)
    fp_same = compute_alert_fingerprint(u1, m1, o1, ct1, sh1)
    assert fp_base == fp_same

    # 2. Different user -> different fingerprint
    fp_diff_user = compute_alert_fingerprint("user-2", m1, o1, ct1, sh1)
    assert fp_base != fp_diff_user

    # 3. Different monitor -> different fingerprint
    fp_diff_mon = compute_alert_fingerprint(u1, "mon-2", o1, ct1, sh1)
    assert fp_base != fp_diff_mon

    # 4. Different offer -> different fingerprint
    fp_diff_offer = compute_alert_fingerprint(u1, m1, "off-2", ct1, sh1)
    assert fp_base != fp_diff_offer

    # 5. Different change_type -> different fingerprint
    fp_diff_ct = compute_alert_fingerprint(u1, m1, o1, "SCHOLARSHIP_OPEN", sh1)
    assert fp_base != fp_diff_ct

    # 6. Different state_hash -> different fingerprint
    fp_diff_sh = compute_alert_fingerprint(u1, m1, o1, ct1, "differentstatehash")
    assert fp_base != fp_diff_sh


# ---------------------------------------------------------------------------
# TEST 17: Offer Deduplication - Cross Provider & Fallback por Fingerprint
# ---------------------------------------------------------------------------
def test_17_offer_deduplication_cross_provider_and_fallback():
    """Confirms external_id scoping per provider and stable fallback fingerprint."""
    # 1. Mesma oferta + mesmo provider -> mesmo fingerprint determinístico
    off1 = NormalizedOffer(
        provider_slug="senac_sp",
        institution_name="Senac São Paulo",
        title="Desenvolvimento Web",
        city="São Paulo",
        modality="presencial",
        shift="Noturno",
        source_url="https://senac.br/web",
    )
    off2 = NormalizedOffer(
        provider_slug="senac_sp",
        institution_name="Senac São Paulo",
        title="Desenvolvimento Web",
        city="São Paulo",
        modality="presencial",
        shift="Noturno",
        source_url="https://senac.br/web",
    )
    assert off1.compute_fingerprint() == off2.compute_fingerprint()

    # 2. Ofertas diferentes sem external_id -> fingerprints diferentes
    off3 = NormalizedOffer(
        provider_slug="senac_sp",
        institution_name="Senac São Paulo",
        title="Enfermagem Geral",
        city="São Paulo",
        modality="presencial",
        shift="Noturno",
        source_url="https://senac.br/enf",
    )
    assert off1.compute_fingerprint() != off3.compute_fingerprint()

    # 3. Mesmo external_id com providers diferentes -> ofertas distintas
    # Validando no motor de matching que evento do SENAI não colide com Senac
    registry = ProviderRegistry()
    registry.register(DummyProvider(slug_name="senac_sp", display_name="Senac SP"))
    registry.register(DummyProvider(slug_name="senai_sp", display_name="SENAI SP"))

    engine = MatchingEngine(registry=registry)

    mon_all = UserMonitor(
        id="mon-all",
        user_id="user-all",
        all_providers=True,
        active=True,
        telegram_chat_id="chat-all",
    )

    ev_senac = OfferChangeEvent(
        offer_id="id-1",
        external_id="COMMOM_ID_999",
        provider_slug="senac_sp",
        title="Eletrônica Básica",
        current_state=OfferState(curso="Eletrônica Básica", status="Aberta", inscricao_disponivel=True),
        url="https://senac.br/eletro",
    )

    ev_senai = OfferChangeEvent(
        offer_id="id-2",
        external_id="COMMOM_ID_999",  # Mesmo external_id!
        provider_slug="senai_sp",
        title="Eletrônica Básica",
        current_state=OfferState(curso="Eletrônica Básica", status="Aberta", inscricao_disponivel=True),
        url="https://senai.br/eletro",
    )

    # Senac gera alerta
    matches_senac = engine.match(ev_senac, [mon_all])
    assert len(matches_senac) == 1

    # SENAI com mesmo external_id NÃO deve ser descartado como duplicata do Senac
    matches_senai = engine.match(ev_senai, [mon_all])
    assert len(matches_senai) == 1
    assert matches_senac[0].fingerprint != matches_senai[0].fingerprint
