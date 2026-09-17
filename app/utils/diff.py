"""Diff utility to compare offer states and detect actionable opportunities."""

from typing import List, Optional
from app.models import OfferState, StateDiff


def compute_offer_diff(
    previous: Optional[OfferState], current: OfferState
) -> StateDiff:
    """Compares previous and current offer states to identify relevant changes."""
    if previous is None:
        # First execution: record initial state, not an alert change
        return StateDiff(
            has_changed=False,
            is_actionable=False,
            reasons=["Estado inicial registrado."],
            previous_state=None,
            current_state=current,
        )

    reasons: List[str] = []
    is_actionable = False

    # 1. Inscrição disponível
    if not previous.inscricao_disponivel and current.inscricao_disponivel:
        reasons.append("Inscrições abertas / Matrícula liberada!")
        is_actionable = True
    elif previous.inscricao_disponivel and not current.inscricao_disponivel:
        reasons.append("Inscrições encerradas ou indisponíveis.")

    # 2. Bolsa disponível
    if not previous.bolsa_disponivel and current.bolsa_disponivel:
        reasons.append("Bolsa de estudo 100% disponível para inscrição!")
        is_actionable = True
    elif previous.bolsa_disponivel and not current.bolsa_disponivel:
        reasons.append("Vagas para bolsa esgotadas ou encerradas.")

    # 3. Mudança de status geral
    if previous.status.strip().lower() != current.status.strip().lower():
        reasons.append(f"Mudança de status: '{previous.status}' ➔ '{current.status}'")
        # If new status contains positive terms
        curr_status_lower = current.status.lower()
        if any(w in curr_status_lower for w in ["abert", "dispon", "vaga", "matr"]):
            is_actionable = True

    # 4. Botões de ação
    prev_buttons = set(b.strip().lower() for b in previous.botoes)
    curr_buttons = set(b.strip().lower() for b in current.botoes)
    new_buttons = curr_buttons - prev_buttons

    if new_buttons:
        reasons.append(f"Novos botões detectados: {', '.join(new_buttons)}")
        # Check if button is actionable
        for b in new_buttons:
            if any(term in b for term in ["inscrev", "compr", "matricul", "bolsa"]):
                is_actionable = True

    # 5. Datas
    if sorted(previous.datas) != sorted(current.datas):
        reasons.append(f"Alteração de datas: {current.datas}")

    # 6. Horários
    if sorted(previous.horarios) != sorted(current.horarios):
        reasons.append(f"Alteração de horários: {current.horarios}")

    # 7. Preço ou parcelas
    if previous.preco and current.preco and previous.preco != current.preco:
        reasons.append(f"Alteração de valores: {previous.preco} ➔ {current.preco}")

    has_changed = len(reasons) > 0

    return StateDiff(
        has_changed=has_changed,
        is_actionable=is_actionable,
        reasons=reasons,
        previous_state=previous,
        current_state=current,
    )
