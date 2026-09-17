"""Tests for XML, JSON and HTML offer parsing."""

from app.scrapers.offer_parser import OfferParser, normalize_shift


def test_parse_offer_sem_vaga(offer_sem_vaga_xml: str):
    """Test parsing an offer that has no open spots."""
    state = OfferParser.parse_api_offer(
        xml_content=offer_sem_vaga_xml,
        course_meta={"tituloComercial": "Técnico em Modelagem do Vestuário"},
        unit_name="Senac Lapa Faustolo",
    )

    assert state.curso == "Técnico em Modelagem do Vestuário"
    assert state.unidade == "Senac Lapa Faustolo"
    assert state.turno == "Noturno"
    assert state.codigo_oferta == "9900357333"
    assert not state.inscricao_disponivel
    assert not state.bolsa_disponivel
    assert "Sem vagas disponíveis" in state.status or "Indisponível" in state.status
    assert any("14/09/2026" in d for d in state.datas)
    assert any("19h às 22h30" in h for h in state.horarios)

    # Check normalized dictionary format
    norm = state.to_normalized_dict()
    assert set(norm.keys()) == {
        "curso",
        "unidade",
        "turno",
        "status",
        "bolsa_disponivel",
        "inscricao_disponivel",
        "datas",
        "horarios",
        "botoes",
        "texto_relevante",
    }


def test_parse_offer_com_vaga(offer_com_vaga_xml: str):
    """Test parsing an offer where regular registration is open."""
    state = OfferParser.parse_api_offer(
        xml_content=offer_com_vaga_xml,
        course_meta={"tituloComercial": "Técnico em Modelagem do Vestuário"},
        unit_name="Senac Lapa Faustolo",
    )

    assert state.inscricao_disponivel is True
    assert state.bolsa_disponivel is False
    assert "Inscrições abertas" in state.status
    assert "Comprar curso" in state.botoes or "Inscrever-se" in state.botoes


def test_parse_offer_bolsa_aberta(offer_bolsa_aberta_xml: str):
    """Test parsing an offer where scholarship registration is open."""
    bolsa_payload = {
        "DATA": [
            {
                "ROWNUM": 1,
                "BOTAO_BOLSA": True,
                "LISTA_ESPERA": False,
                "TEM_VAGA_BOLSA": True,
                "DATA_ABERTURA": "2026-08-25T12:00:00-03:00",
                "COD_EVENTO": "9900357333",
            }
        ]
    }

    state = OfferParser.parse_api_offer(
        xml_content=offer_bolsa_aberta_xml,
        bolsa_data=bolsa_payload,
        course_meta={"tituloComercial": "Técnico em Modelagem do Vestuário"},
        unit_name="Senac Lapa Faustolo",
    )

    assert state.bolsa_disponivel is True
    assert "Bolsa disponível" in state.status
    assert "Inscrever para bolsa de estudo" in state.botoes


def test_parse_html_fallback(sample_page_html: str):
    """Test parsing standard HTML page as fallback."""
    state = OfferParser.parse_html_offer(
        html=sample_page_html,
        target_offer_id="9900357333",
        default_course="Técnico em Modelagem do Vestuário",
        default_unit="Senac Lapa Faustolo",
    )

    assert state.curso == "Técnico em Modelagem do Vestuário"
    assert state.unidade == "Senac Lapa Faustolo"
    assert state.turno == "Noturno"
    assert state.inscricao_disponivel is True
    assert state.bolsa_disponivel is True
    assert "Comprar curso" in state.botoes


def test_normalize_shift():
    """Test shift conversion and normalization."""
    assert normalize_shift("NO") == "Noturno"
    assert normalize_shift("MA") == "Manhã"
    assert normalize_shift("TA") == "Tarde"
    assert normalize_shift(None, "Aulas das 19h às 22h") == "Noturno"
    assert normalize_shift(None, "Aulas das 8h às 12h") == "Manhã"
    assert normalize_shift(None, "Aulas das 14h às 18h") == "Tarde"
