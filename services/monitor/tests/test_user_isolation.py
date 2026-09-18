"""Multi-user isolation and cross-course alert rejection tests."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from app.matching import MatchingEngine, OfferChangeEvent, UserMonitor
from app.models import OfferState, StateDiff
from app.notifications.telegram import TelegramProvider
from app.worker import CourseWorker


def test_user_a_gastronomia_vs_user_b_marketing_cross_notification_isolation():
    """CRITICAL TEST: Ensures User A (Gastronomia) and User B (Marketing) never receive cross alerts,
    and neither receives alerts for 'Modelagem do Vestuário'.
    """
    engine = MatchingEngine()

    # User A monitors Gastronomia
    mon_a = UserMonitor(
        id="mon-user-a",
        user_id="user-a-gastronomia",
        query_text="Gastronomia",
        all_providers=True,
        active=True,
        telegram_chat_id="chat-111111",
    )

    # User B monitors Marketing
    mon_b = UserMonitor(
        id="mon-user-b",
        user_id="user-b-marketing",
        query_text="Marketing",
        all_providers=True,
        active=True,
        telegram_chat_id="chat-222222",
    )

    # User C monitors Modelagem
    mon_c = UserMonitor(
        id="mon-user-c",
        user_id="user-c-modelagem",
        query_text="Técnico em Modelagem do Vestuário",
        all_providers=True,
        active=True,
        telegram_chat_id="chat-333333",
    )

    all_monitors = [mon_a, mon_b, mon_c]

    # 1. Event: Modelagem do Vestuário
    state_modelagem = OfferState(
        curso="Técnico em Modelagem do Vestuário",
        unidade="Senac Lapa Faustolo",
        turno="Noturno",
        status="Inscrições abertas",
        inscricao_disponivel=True,
        codigo_oferta="9900357333",
    )
    event_modelagem = OfferChangeEvent(
        offer_id="9900357333",
        provider_slug="senac_sp",
        title="Técnico em Modelagem do Vestuário",
        city="Senac Lapa Faustolo",
        shift="Noturno",
        change_type="ENROLLMENT_OPEN",
        current_state=state_modelagem,
        url="https://www.sp.senac.br/modelagem",
    )

    matches_modelagem = engine.match(event_modelagem, all_monitors)

    # ONLY User C must receive Modelagem!
    assert len(matches_modelagem) == 1
    assert matches_modelagem[0].user_id == "user-c-modelagem"
    assert matches_modelagem[0].telegram_chat_id == "chat-333333"
    assert "Modelagem do Vestuário" in matches_modelagem[0].message
    # User A and User B received ZERO alerts!
    assert not any(m.user_id == "user-a-gastronomia" for m in matches_modelagem)
    assert not any(m.user_id == "user-b-marketing" for m in matches_modelagem)

    # 2. Event: Gastronomia
    state_gastro = OfferState(
        curso="Técnico em Gastronomia",
        unidade="Senac Aclimação",
        turno="Manhã",
        status="Bolsa disponível",
        bolsa_disponivel=True,
        codigo_oferta="9900444444",
    )
    event_gastro = OfferChangeEvent(
        offer_id="9900444444",
        provider_slug="senac_sp",
        title="Técnico em Gastronomia",
        city="Senac Aclimação",
        shift="Manhã",
        change_type="SCHOLARSHIP_OPEN",
        current_state=state_gastro,
        url="https://www.sp.senac.br/gastronomia",
        bolsa_disponivel=True,
    )

    engine_gastro = MatchingEngine()  # fresh engine without deduplication memory
    matches_gastro = engine_gastro.match(event_gastro, all_monitors)

    # ONLY User A must receive Gastronomia!
    assert len(matches_gastro) == 1
    assert matches_gastro[0].user_id == "user-a-gastronomia"
    assert matches_gastro[0].telegram_chat_id == "chat-111111"
    assert "Gastronomia" in matches_gastro[0].message
    # User B and User C received ZERO alerts!
    assert not any(m.user_id == "user-b-marketing" for m in matches_gastro)
    assert not any(m.user_id == "user-c-modelagem" for m in matches_gastro)

    # 3. Event: Marketing
    state_mkt = OfferState(
        curso="Técnico em Marketing",
        unidade="Senac Lapa Tito",
        turno="Noturno",
        status="Inscrições abertas",
        inscricao_disponivel=True,
        codigo_oferta="9900555555",
    )
    event_mkt = OfferChangeEvent(
        offer_id="9900555555",
        provider_slug="senac_sp",
        title="Técnico em Marketing",
        city="Senac Lapa Tito",
        shift="Noturno",
        change_type="ENROLLMENT_OPEN",
        current_state=state_mkt,
        url="https://www.sp.senac.br/marketing",
    )

    engine_mkt = MatchingEngine()
    matches_mkt = engine_mkt.match(event_mkt, all_monitors)

    # ONLY User B must receive Marketing!
    assert len(matches_mkt) == 1
    assert matches_mkt[0].user_id == "user-b-marketing"
    assert matches_mkt[0].telegram_chat_id == "chat-222222"
    assert "Marketing" in matches_mkt[0].message
    # User A and User C received ZERO alerts!
    assert not any(m.user_id == "user-a-gastronomia" for m in matches_mkt)
    assert not any(m.user_id == "user-c-modelagem" for m in matches_mkt)


@pytest.mark.asyncio
async def test_telegram_provider_never_broadcasts():
    """Verifies that send_offer_alert and send_new_offer_alert send only to the specified recipient,
    never broadcasting to all linked accounts.
    """
    provider = TelegramProvider(bot_token="fake-token")
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=True)
    provider._bot = mock_bot

    state = OfferState(
        curso="Técnico em Gastronomia",
        unidade="Senac Aclimação",
        turno="Manhã",
        status="Inscrições abertas",
    )
    diff = StateDiff(has_changed=True, current_state=state, detected_at=__import__("datetime").datetime.now())

    # Send to User A only
    sent = await provider.send_offer_alert(diff, "https://senac.br", recipient_id="chat-111111")
    assert sent is True
    assert mock_bot.send_message.call_count == 1
    call_args = mock_bot.send_message.call_args[1]
    assert call_args["chat_id"] == "chat-111111"
    assert "Gastronomia" in call_args["text"]


@pytest.mark.asyncio
async def test_worker_persists_alerts_to_supabase():
    """Verifies that CourseWorker._persist_supabase_alert writes the alert to Supabase alerts table."""
    mock_supabase = MagicMock()
    mock_table = MagicMock()
    mock_supabase.table.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{"id": "alert-1"}])

    mock_repo = MagicMock()
    mock_repo.supabase = mock_supabase

    worker = CourseWorker(worker_id="test-worker", monitor_repo=mock_repo)

    from app.matching import MatchResult

    match = MatchResult(
        user_id="user-123",
        monitor_id="mon-456",
        offer_id="off-789",
        telegram_chat_id="chat-999",
        change_type="ENROLLMENT_OPEN",
        fingerprint="fp-abcdef123456",
        message="Vaga Aberta!",
    )

    await worker._persist_supabase_alert(match)

    mock_supabase.table.assert_called_with("alerts")
    mock_table.upsert.assert_called_once()
    payload = mock_table.upsert.call_args[0][0]
    assert payload["user_id"] == "user-123"
    assert payload["monitor_id"] == "mon-456"
    assert payload["alert_type"] == "ENROLLMENT_OPEN"
    assert payload["fingerprint"] == "fp-abcdef123456"
    assert payload["channel"] == "telegram"
    assert payload["delivered"] is True
    assert payload["message_content"] == "Vaga Aberta!"


@pytest.mark.asyncio
async def test_check_executes_only_active_monitors_for_user():
    """TEST 1: User with Monitor A (active=true), Monitor B (active=true), Monitor C (active=false).
    /check must execute exactly A and B.
    """
    mock_repo = MagicMock()
    mon_a = UserMonitor(id="mon-a", user_id="user-1", query_text="Curso A", active=True)
    mon_b = UserMonitor(id="mon-b", user_id="user-1", query_text="Curso B", active=True)

    # get_user_monitors with active_only=True returns only A and B
    mock_repo.get_user_monitors = AsyncMock(return_value=[mon_a, mon_b])

    mock_link_mgr = MagicMock()
    mock_link_mgr.get_account_by_chat.return_value = MagicMock(user_id="user-1")
    mock_link_mgr.list_active_accounts.return_value = [
        MagicMock(user_id="user-1", telegram_chat_id="chat-1", active=True)
    ]

    mock_provider = MagicMock()
    del mock_provider.search_offers_structured
    mock_provider.name = "Test Provider"
    mock_provider.search_offers = AsyncMock(return_value=[])

    mock_registry = MagicMock()
    mock_registry.get_active_providers.return_value = {"test_prov": mock_provider}

    worker = CourseWorker(
        worker_id="test-worker",
        monitor_repo=mock_repo,
        link_manager=mock_link_mgr,
        registry=mock_registry,
    )

    res = await worker.run_user_check(chat_id="chat-1")

    assert "2 monitor(es) ativo(s)" in res
    assert "[1] Curso A" in res
    assert "[2] Curso B" in res
    assert mock_provider.search_offers.call_count == 2


@pytest.mark.asyncio
async def test_check_dynamically_detects_new_monitor_without_worker_restart():
    """TEST 2: Worker running with Monitor A in memory; Monitor D is created in Supabase.
    Without restarting worker, /check must execute A and D immediately.
    """
    mon_a = UserMonitor(id="mon-a", user_id="user-1", query_text="Curso A", active=True)
    mon_d = UserMonitor(id="mon-d", user_id="user-1", query_text="Curso D", active=True)

    mock_repo = MagicMock()
    # First call had only mon_a; now Supabase has mon_a and mon_d
    mock_repo.get_user_monitors = AsyncMock(return_value=[mon_a, mon_d])

    mock_link_mgr = MagicMock()
    mock_link_mgr.get_account_by_chat.return_value = MagicMock(user_id="user-1")
    mock_link_mgr.list_active_accounts.return_value = [
        MagicMock(user_id="user-1", telegram_chat_id="chat-1", active=True)
    ]

    mock_provider = MagicMock()
    del mock_provider.search_offers_structured
    mock_provider.name = "Test Provider"
    mock_provider.search_offers = AsyncMock(return_value=[])

    mock_registry = MagicMock()
    mock_registry.get_active_providers.return_value = {"test_prov": mock_provider}

    worker = CourseWorker(
        worker_id="test-worker",
        monitor_repo=mock_repo,
        link_manager=mock_link_mgr,
        registry=mock_registry,
    )
    # Simulate worker had only mon_a in memory from previous startup
    worker.active_monitors = [mon_a]

    res = await worker.run_user_check(chat_id="chat-1")

    assert "2 monitor(es) ativo(s)" in res
    assert "Curso A" in res
    assert "Curso D" in res
    # Confirms worker's internal active_monitors was also updated
    assert any(m.id == "mon-d" for m in worker.active_monitors)


@pytest.mark.asyncio
async def test_check_ignores_monitor_paused_on_dashboard_without_restart():
    """TEST 3: Monitor B is paused on dashboard (active=False in Supabase).
    Without restarting worker, /check must NOT execute Monitor B.
    """
    mon_a = UserMonitor(id="mon-a", user_id="user-1", query_text="Curso A", active=True)
    mon_b = UserMonitor(id="mon-b", user_id="user-1", query_text="Curso B", active=False)

    mock_repo = MagicMock()
    # Supabase returns only active monitors when active_only=True
    mock_repo.get_user_monitors = AsyncMock(return_value=[mon_a])

    mock_link_mgr = MagicMock()
    mock_link_mgr.get_account_by_chat.return_value = MagicMock(user_id="user-1")
    mock_link_mgr.list_active_accounts.return_value = [
        MagicMock(user_id="user-1", telegram_chat_id="chat-1", active=True)
    ]

    mock_provider = MagicMock()
    del mock_provider.search_offers_structured
    mock_provider.name = "Test Provider"
    mock_provider.search_offers = AsyncMock(return_value=[])

    mock_registry = MagicMock()
    mock_registry.get_active_providers.return_value = {"test_prov": mock_provider}

    worker = CourseWorker(
        worker_id="test-worker",
        monitor_repo=mock_repo,
        link_manager=mock_link_mgr,
        registry=mock_registry,
    )
    # Worker had both in memory previously
    worker.active_monitors = [mon_a, mon_b]

    res = await worker.run_user_check(chat_id="chat-1")

    assert "1 monitor(es) ativo(s)" in res
    assert "Curso A" in res
    assert "Curso B" not in res
    # Confirms paused mon_b was also purged from worker's active_monitors
    assert not any(m.id == "mon-b" for m in worker.active_monitors)


@pytest.mark.asyncio
async def test_check_resumes_reactivated_monitor_immediately():
    """TEST 4: Monitor B is reactivated in Supabase.
    /check must immediately include Monitor B again without restarting worker.
    """
    mon_a = UserMonitor(id="mon-a", user_id="user-1", query_text="Curso A", active=True)
    mon_b = UserMonitor(id="mon-b", user_id="user-1", query_text="Curso B", active=True)

    mock_repo = MagicMock()
    mock_repo.get_user_monitors = AsyncMock(return_value=[mon_a, mon_b])

    mock_link_mgr = MagicMock()
    mock_link_mgr.get_account_by_chat.return_value = MagicMock(user_id="user-1")
    mock_link_mgr.list_active_accounts.return_value = [
        MagicMock(user_id="user-1", telegram_chat_id="chat-1", active=True)
    ]

    mock_provider = MagicMock()
    del mock_provider.search_offers_structured
    mock_provider.name = "Test Provider"
    mock_provider.search_offers = AsyncMock(return_value=[])

    mock_registry = MagicMock()
    mock_registry.get_active_providers.return_value = {"test_prov": mock_provider}

    worker = CourseWorker(
        worker_id="test-worker",
        monitor_repo=mock_repo,
        link_manager=mock_link_mgr,
        registry=mock_registry,
    )
    # Worker had only mon_a in memory
    worker.active_monitors = [mon_a]

    res = await worker.run_user_check(chat_id="chat-1")

    assert "2 monitor(es) ativo(s)" in res
    assert "Curso A" in res
    assert "Curso B" in res


@pytest.mark.asyncio
async def test_check_supabase_failure_returns_friendly_error_without_using_stale_cache():
    """TEST 5: Supabase failure during /check.
    Must NOT execute stale cache, must return friendly message, and trigger zero alerts.
    """
    mock_repo = MagicMock()
    mock_repo.get_user_monitors = AsyncMock(side_effect=Exception("Database connection timeout"))

    mock_link_mgr = MagicMock()
    mock_link_mgr.get_account_by_chat.return_value = MagicMock(user_id="user-1")

    mock_provider = MagicMock()
    mock_provider.search_offers = AsyncMock()

    mock_registry = MagicMock()
    mock_registry.get_active_providers.return_value = {"test_prov": mock_provider}

    worker = CourseWorker(
        worker_id="test-worker",
        monitor_repo=mock_repo,
        link_manager=mock_link_mgr,
        registry=mock_registry,
    )
    # Stale monitor in memory
    worker.active_monitors = [
        UserMonitor(id="mon-stale", user_id="user-1", query_text="Curso Stale", active=True)
    ]

    res = await worker.run_user_check(chat_id="chat-1")

    assert "Não foi possível carregar seus monitoramentos agora. Tente novamente em alguns instantes." in res
    assert mock_provider.search_offers.call_count == 0


@pytest.mark.asyncio
async def test_check_multi_user_isolation_never_loads_other_user_monitors():
    """TEST 6: /check for User A must NEVER execute User B's monitors."""
    mon_a = UserMonitor(id="mon-a", user_id="user-a", query_text="Gastronomia", active=True)
    mon_b = UserMonitor(id="mon-b", user_id="user-b", query_text="Marketing", active=True)

    mock_repo = MagicMock()
    async def get_user_monitors_side_effect(user_id: str, active_only: bool = False):
        if user_id == "user-a":
            return [mon_a]
        elif user_id == "user-b":
            return [mon_b]
        return []

    mock_repo.get_user_monitors = AsyncMock(side_effect=get_user_monitors_side_effect)

    mock_link_mgr = MagicMock()
    def get_account_side_effect(chat_id: str):
        if chat_id == "chat-user-a":
            return MagicMock(user_id="user-a")
        elif chat_id == "chat-user-b":
            return MagicMock(user_id="user-b")
        return None

    mock_link_mgr.get_account_by_chat.side_effect = get_account_side_effect
    mock_link_mgr.list_active_accounts.return_value = [
        MagicMock(user_id="user-a", telegram_chat_id="chat-user-a", active=True),
        MagicMock(user_id="user-b", telegram_chat_id="chat-user-b", active=True),
    ]

    mock_provider = MagicMock()
    del mock_provider.search_offers_structured
    mock_provider.name = "Test Provider"
    mock_provider.search_offers = AsyncMock(return_value=[])

    mock_registry = MagicMock()
    mock_registry.get_active_providers.return_value = {"test_prov": mock_provider}

    worker = CourseWorker(
        worker_id="test-worker",
        monitor_repo=mock_repo,
        link_manager=mock_link_mgr,
        registry=mock_registry,
    )
    # Memory has both users' monitors
    worker.active_monitors = [mon_a, mon_b]

    # Run check for User A
    res_a = await worker.run_user_check(chat_id="chat-user-a")
    assert "1 monitor(es) ativo(s)" in res_a
    assert "Gastronomia" in res_a
    assert "Marketing" not in res_a

    # Run check for User B
    res_b = await worker.run_user_check(chat_id="chat-user-b")
    assert "1 monitor(es) ativo(s)" in res_b
    assert "Marketing" in res_b
    assert "Gastronomia" not in res_b
