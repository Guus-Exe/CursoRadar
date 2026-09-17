"""Dedicated tests for shift normalization and conflict resolution.

Addresses the discovered inconsistency where an offer was marked 'Noturno'
even though the classroom schedule stated '8h às 12h' (morning).
"""

import pytest
from app.scrapers.offer_parser import normalize_shift, OfferParser


def test_normalize_shift_standard_codes():
    """Validates normalization from institution period codes."""
    assert normalize_shift("NO") == "Noturno"
    assert normalize_shift("noturno") == "Noturno"
    assert normalize_shift("MA") == "Manhã"
    assert normalize_shift("manha") == "Manhã"
    assert normalize_shift("manhã") == "Manhã"
    assert normalize_shift("TA") == "Tarde"
    assert normalize_shift("tarde") == "Tarde"
    assert normalize_shift("IN") == "Integral"
    assert normalize_shift("SAB") == "Sábado"


def test_normalize_shift_from_hours_text():
    """Validates shift extraction from schedule text strings."""
    # Single digit hours (previously failed with \d{2} regex)
    assert normalize_shift(None, "Aulas das 8h às 12h") == "Manhã"
    assert normalize_shift(None, "Seg a Sex das 8h às 12h30") == "Manhã"
    assert normalize_shift(None, "8:00 às 12:00") == "Manhã"
    assert normalize_shift(None, "07:30 às 11:30") == "Manhã"

    # Afternoon
    assert normalize_shift(None, "Aulas das 13h30 às 17h30") == "Tarde"
    assert normalize_shift(None, "14h às 18h") == "Tarde"

    # Evening
    assert normalize_shift(None, "Seg a Sex das 19h às 22h30") == "Noturno"
    assert normalize_shift(None, "18h30 às 22h") == "Noturno"


def test_normalize_shift_resolves_conflict_between_code_and_hours():
    """CRITICAL: If code says 'NO' (Noturno) but the hours clearly say '8h às 12h' (morning),
    the physical schedule must take precedence to prevent misleading users!"""
    result = normalize_shift("NO", "Seg a Sex das 8h às 12h")
    assert result == "Manhã", "Schedule 8h às 12h must override conflicting 'NO' shift code!"

    result_afternoon = normalize_shift("NO", "Seg a Sex das 14h às 18h")
    assert result_afternoon == "Tarde", "Schedule 14h às 18h must override conflicting 'NO' shift code!"

    # When hours agree with code, keeps code
    assert normalize_shift("NO", "Seg a Sex das 19h às 22h30") == "Noturno"
    assert normalize_shift("MA", "Seg a Sex das 8h às 12h") == "Manhã"


def test_parse_html_offer_does_not_default_to_noturno_for_morning_class():
    """Validates that HTML parser does not blindly default to 'Noturno' for 8h classes."""
    html_morning = """
    <html>
    <body>
        <h1>Técnico em Administração</h1>
        <div class="breadcrumb"><span>Senac Lapa Faustolo</span></div>
        <p>Aulas presenciais: 8h às 12h</p>
        <button class="cta-card-oferta">Comprar curso</button>
    </body>
    </html>
    """
    state = OfferParser.parse_html_offer(
        html=html_morning,
        target_offer_id="9900123456",
        default_course="Técnico em Administração",
        default_unit="Senac Lapa Faustolo",
    )
    assert state.turno == "Manhã"
