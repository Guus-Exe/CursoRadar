"""Tests for state diffing and change detection."""

from app.models import OfferState
from app.utils.diff import compute_offer_diff


def test_diff_initial_state():
    """Initial check should record baseline without triggering false alert."""
    curr = OfferState(
        curso="Técnico em Modelagem do Vestuário",
        unidade="Senac Lapa Faustolo",
        turno="Noturno",
        status="Sem vagas disponíveis",
        bolsa_disponivel=False,
        inscricao_disponivel=False,
    )
    diff = compute_offer_diff(None, curr)
    assert not diff.has_changed
    assert not diff.is_actionable


def test_diff_no_changes():
    """Identical states should produce no diff."""
    state1 = OfferState(
        curso="Técnico em Modelagem do Vestuário",
        unidade="Senac Lapa Faustolo",
        turno="Noturno",
        status="Sem vagas disponíveis",
        bolsa_disponivel=False,
        inscricao_disponivel=False,
        datas=["Início: 14/09/2026"],
    )
    state2 = state1.model_copy()
    diff = compute_offer_diff(state1, state2)
    assert not diff.has_changed
    assert not diff.is_actionable


def test_diff_inscricao_aberta():
    """Detect when regular subscription becomes available."""
    prev = OfferState(
        curso="Técnico em Modelagem do Vestuário",
        unidade="Senac Lapa Faustolo",
        turno="Noturno",
        status="Sem vagas disponíveis",
        bolsa_disponivel=False,
        inscricao_disponivel=False,
        botoes=["Registrar interesse"],
    )
    curr = prev.model_copy(
        update={
            "status": "Inscrições abertas",
            "inscricao_disponivel": True,
            "botoes": ["Comprar curso", "Inscrever-se"],
        }
    )
    diff = compute_offer_diff(prev, curr)
    assert diff.has_changed is True
    assert diff.is_actionable is True
    assert any("Inscrições abertas" in r for r in diff.reasons)


def test_diff_bolsa_disponivel():
    """Detect when scholarship becomes available."""
    prev = OfferState(
        curso="Técnico em Modelagem do Vestuário",
        unidade="Senac Lapa Faustolo",
        turno="Noturno",
        status="Sem vagas disponíveis",
        bolsa_disponivel=False,
        inscricao_disponivel=False,
    )
    curr = prev.model_copy(
        update={
            "status": "Bolsa disponível",
            "bolsa_disponivel": True,
            "botoes": ["Inscrever para bolsa de estudo"],
        }
    )
    diff = compute_offer_diff(prev, curr)
    assert diff.has_changed is True
    assert diff.is_actionable is True
    assert any("Bolsa de estudo" in r for r in diff.reasons)


def test_diff_dates_or_hours_changed():
    """Detect when schedule or dates change."""
    prev = OfferState(
        curso="Técnico em Modelagem do Vestuário",
        unidade="Senac Lapa Faustolo",
        turno="Noturno",
        datas=["Início: 14/09/2026"],
        horarios=["19h às 22h30"],
    )
    curr = prev.model_copy(
        update={
            "datas": ["Início: 21/09/2026"],
            "horarios": ["19h às 22h00"],
        }
    )
    diff = compute_offer_diff(prev, curr)
    assert diff.has_changed is True
    assert any("Alteração de datas" in r for r in diff.reasons)
    assert any("Alteração de horários" in r for r in diff.reasons)
