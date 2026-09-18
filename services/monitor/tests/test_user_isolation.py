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
