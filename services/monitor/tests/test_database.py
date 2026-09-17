"""Tests for SQLite database persistence and duplicate alert prevention."""

from app.database import Database
from app.models import OfferState, StateDiff


def test_db_upsert_and_retrieve(temp_db: Database):
    """Test saving and loading offer states from SQLite."""
    state = OfferState(
        curso="Técnico em Modelagem do Vestuário",
        unidade="Senac Lapa Faustolo",
        turno="Noturno",
        status="Sem vagas disponíveis",
        codigo_oferta="9900357333",
    )

    temp_db.upsert_offer(
        offer_id="9900357333",
        curso=state.curso,
        unidade=state.unidade,
        turno=state.turno,
        url="https://www.sp.senac.br",
        state=state,
    )

    loaded = temp_db.get_last_state("9900357333")
    assert loaded is not None
    assert loaded.curso == "Técnico em Modelagem do Vestuário"
    assert loaded.codigo_oferta == "9900357333"


def test_db_record_check(temp_db: Database):
    """Test recording execution check history."""
    state = OfferState(
        curso="Técnico em Modelagem do Vestuário",
        unidade="Senac Lapa Faustolo",
        turno="Noturno",
        status="Inscrições abertas",
    )
    diff = StateDiff(
        has_changed=True,
        is_actionable=True,
        reasons=["Inscrições abertas"],
        current_state=state,
    )

    temp_db.record_check(
        offer_id="9900357333",
        is_success=True,
        status_code=200,
        state=state,
        diff=diff,
    )

    last_check = temp_db.get_last_check("9900357333")
    assert last_check is not None
    assert last_check.is_success is True
    assert last_check.status_code == 200


def test_duplicate_alert_prevention(temp_db: Database):
    """Test that identical alerts are prevented from sending repeatedly."""
    offer_id = "9900357333"
    state_hash = "abc123hash"

    # Initially, it is not a duplicate
    assert not temp_db.is_duplicate_alert(
        alert_type="VAGA_ENCONTRADA",
        offer_id=offer_id,
        state_hash=state_hash,
        channel="telegram",
        cooldown_hours=6,
    )

    # Record the alert dispatch
    temp_db.record_alert(
        alert_type="VAGA_ENCONTRADA",
        offer_id=offer_id,
        state_hash=state_hash,
        message_content="🚨 VAGA ENCONTRADA",
        channel="telegram",
    )

    # Now it must be detected as duplicate within cooldown window
    assert temp_db.is_duplicate_alert(
        alert_type="VAGA_ENCONTRADA",
        offer_id=offer_id,
        state_hash=state_hash,
        channel="telegram",
        cooldown_hours=6,
    )

    # Different state hash should not be considered duplicate
    assert not temp_db.is_duplicate_alert(
        alert_type="VAGA_ENCONTRADA",
        offer_id=offer_id,
        state_hash="different_hash",
        channel="telegram",
        cooldown_hours=6,
    )


def test_db_settings_pause_resume(temp_db: Database):
    """Test reading and writing settings."""
    assert temp_db.get_setting("is_paused", "false") == "false"
    temp_db.set_setting("is_paused", "true")
    assert temp_db.get_setting("is_paused") == "true"
