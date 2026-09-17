"""Tests for MatchingEngine, 100-user simulation, and multi-user deduplication."""

import pytest
from app.models import OfferState
from app.matching import (
    MatchingEngine,
    MonitorPreferences,
    OfferChangeEvent,
    UserMonitor,
    compute_alert_fingerprint,
)


def test_matching_100_users_single_offer_query():
    """Requirement: 100 users monitor the same opportunity.
    1 offer check -> 100 matches -> 100 independent alerts -> 0 duplicates on re-run.
    """
    institution_id = "inst-1"
    location_id = "loc-lapa"
    course_id = "course-vestuario"

    # Create 100 unique user monitors
    monitors = []
    for i in range(100):
        monitors.append(
            UserMonitor(
                id=f"monitor-{i}",
                user_id=f"user-{i}",
                institution_id=institution_id,
                location_id=location_id,
                course_id=course_id,
                shift="Noturno" if i % 2 == 0 else None,  # Half specify Noturno, half accept any shift
                active=True,
                preferences=MonitorPreferences(
                    notify_scholarship=True,
                    notify_paid=True,
                    notify_enrollment_open=True,
                ),
                telegram_chat_id=f"chat-{i}",
            )
        )

    # Opportunity event: regular and scholarship open on evening shift
    current_state = OfferState(
        curso="Técnico em Modelagem do Vestuário",
        unidade="Senac Lapa Faustolo",
        turno="Noturno",
        status="Inscrições abertas e Bolsa disponível",
        bolsa_disponivel=True,
        inscricao_disponivel=True,
        codigo_oferta="9900357333",
        botoes=["Comprar curso", "Inscrever para bolsa de estudo"],
    )

    event = OfferChangeEvent(
        offer_id="9900357333",
        institution_id=institution_id,
        location_id=location_id,
        course_id=course_id,
        shift="Noturno",
        change_type="ENROLLMENT_OPEN",
        reasons=["Inscrições abertas / Matrícula liberada!", "Bolsa disponível"],
        current_state=current_state,
        url="https://www.sp.senac.br/oferta/9900357333",
    )

    engine = MatchingEngine()

    # Step 1: Execute matching
    results = engine.match(event, monitors)

    # All 100 users must receive their individual, customized notification!
    assert len(results) == 100
    assert len(set(r.user_id for r in results)) == 100
    assert len(set(r.telegram_chat_id for r in results)) == 100
    assert len(set(r.fingerprint for r in results)) == 100

    for r in results:
        assert "Técnico em Modelagem do Vestuário" in r.message
        assert "Senac Lapa Faustolo" in r.message
        assert "https://www.sp.senac.br/oferta/9900357333" in r.message

    # Step 2: Re-run with the same event (e.g. next check cycle, offer still open)
    repeat_results = engine.match(event, monitors)
    # Deduplication must discard all 100 as duplicates!
    assert len(repeat_results) == 0, "Deduplication must prevent sending identical alerts!"


def test_matching_shift_filtering():
    """Ensures a user monitoring 'Manhã' does NOT receive an alert for 'Noturno'."""
    mon_morning = UserMonitor(
        id="mon-morning",
        user_id="user-1",
        institution_id="inst-1",
        location_id="loc-1",
        course_id="course-1",
        shift="Manhã",
        active=True,
        telegram_chat_id="chat-1",
    )
    mon_evening = UserMonitor(
        id="mon-evening",
        user_id="user-2",
        institution_id="inst-1",
        location_id="loc-1",
        course_id="course-1",
        shift="Noturno",
        active=True,
        telegram_chat_id="chat-2",
    )

    state = OfferState(
        curso="Técnico em Informática",
        unidade="Senac Lapa Tito",
        turno="Noturno",
        status="Inscrições abertas",
        inscricao_disponivel=True,
        codigo_oferta="9900111111",
    )
    event = OfferChangeEvent(
        offer_id="9900111111",
        institution_id="inst-1",
        location_id="loc-1",
        course_id="course-1",
        shift="Noturno",
        change_type="ENROLLMENT_OPEN",
        current_state=state,
        url="https://www.sp.senac.br/oferta/9900111111",
    )

    engine = MatchingEngine()
    results = engine.match(event, [mon_morning, mon_evening])

    assert len(results) == 1
    assert results[0].user_id == "user-2"
    assert results[0].telegram_chat_id == "chat-2"


def test_matching_preference_filtering():
    """Ensures users interested only in scholarship do not receive paid-only alerts."""
    mon_scholarship_only = UserMonitor(
        id="mon-bolsa",
        user_id="user-bolsa",
        institution_id="inst-1",
        location_id="loc-1",
        course_id="course-1",
        active=True,
        preferences=MonitorPreferences(
            notify_scholarship=True,
            notify_paid=False,
            notify_enrollment_open=False,
        ),
        telegram_chat_id="chat-bolsa",
    )
    mon_paid_only = UserMonitor(
        id="mon-pago",
        user_id="user-pago",
        institution_id="inst-1",
        location_id="loc-1",
        course_id="course-1",
        active=True,
        preferences=MonitorPreferences(
            notify_scholarship=False,
            notify_paid=True,
            notify_enrollment_open=True,
        ),
        telegram_chat_id="chat-pago",
    )

    state_paid = OfferState(
        curso="Técnico em Administração",
        unidade="Senac Lapa Faustolo",
        turno="Noturno",
        status="Inscrições abertas",
        bolsa_disponivel=False,
        inscricao_disponivel=True,
        codigo_oferta="9900222222",
    )
    event_paid = OfferChangeEvent(
        offer_id="9900222222",
        institution_id="inst-1",
        location_id="loc-1",
        course_id="course-1",
        shift="Noturno",
        change_type="ENROLLMENT_OPEN",
        current_state=state_paid,
        url="https://www.sp.senac.br/oferta/9900222222",
    )

    engine = MatchingEngine()
    results = engine.match(event_paid, [mon_scholarship_only, mon_paid_only])

    assert len(results) == 1
    assert results[0].user_id == "user-pago"
