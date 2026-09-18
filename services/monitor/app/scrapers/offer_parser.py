"""Parser for Senac course and offer data from XML, JSON, and HTML."""

from datetime import datetime
import json
import re
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from app.models import OfferState
from app.utils.logger import logger


SHIFT_MAP = {
    "no": "Noturno",
    "noturno": "Noturno",
    "noite": "Noturno",
    "ma": "Manhã",
    "manha": "Manhã",
    "manhã": "Manhã",
    "ta": "Tarde",
    "tarde": "Tarde",
    "in": "Integral",
    "integral": "Integral",
    "sab": "Sábado",
    "sabado": "Sábado",
}


def normalize_shift(raw_shift: Optional[str], hours_text: Optional[str] = None) -> str:
    """Normalizes period/shift text to human-readable form.
    
    If hours_text provides a clear unambiguous class schedule (e.g. 8h às 12h),
    it validates or overrides conflicting raw_shift codes to prevent misleading users.
    """
    derived_from_hours = None
    if hours_text:
        h_clean = hours_text.lower()
        if any(w in h_clean for w in ["noturno", "noite"]):
            derived_from_hours = "Noturno"
        elif any(w in h_clean for w in ["tarde", "vespertino"]):
            derived_from_hours = "Tarde"
        elif any(w in h_clean for w in ["manhã", "manha", "matutino"]):
            derived_from_hours = "Manhã"
        else:
            # Match starting hour: accepts single or double digit hours, e.g. "8h", "08h", "8:00", "14h"
            match = re.search(r'(?:das\s*|de\s*)?(\d{1,2})(?::\d{2})?h?', h_clean)
            if match:
                try:
                    start_hour = int(match.group(1))
                    if 18 <= start_hour <= 23:
                        derived_from_hours = "Noturno"
                    elif 12 <= start_hour < 18:
                        derived_from_hours = "Tarde"
                    elif 5 <= start_hour < 12:
                        derived_from_hours = "Manhã"
                except ValueError:
                    pass

    normalized_raw = None
    if raw_shift:
        clean = raw_shift.strip().lower()
        if clean in SHIFT_MAP:
            normalized_raw = SHIFT_MAP[clean]
        else:
            for key, val in SHIFT_MAP.items():
                if key in clean:
                    normalized_raw = val
                    break

    # If hours unambiguously indicate a shift different from raw_shift, schedule takes precedence!
    if derived_from_hours:
        if normalized_raw and normalized_raw != derived_from_hours:
            logger.warning(
                f"Divergência detectada entre código de turno '{raw_shift}' ({normalized_raw}) "
                f"e horário da aula '{hours_text}' ({derived_from_hours}). Prevalecendo horário físico."
            )
        return derived_from_hours

    if normalized_raw:
        return normalized_raw

    return raw_shift.strip() if raw_shift else "Não informado"


def _format_date(date_str: Optional[str]) -> Optional[str]:
    """Formats YYYY-MM-DD to DD/MM/YYYY."""
    if not date_str:
        return None
    date_clean = date_str.split("T")[0].strip()
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", date_clean)
    if match:
        return f"{match.group(3)}/{match.group(2)}/{match.group(1)}"
    return date_clean


def parse_xml_dynamic_elements(xml_string: str) -> Dict[str, Any]:
    """Parses Liferay dynamic-element XML structure into dictionary."""
    fields: Dict[str, Any] = {}
    if not xml_string or not xml_string.strip():
        return fields

    try:
        root = ET.fromstring(xml_string)
        for elem in root.findall(".//dynamic-element"):
            name = elem.get("name") or elem.get("field-reference")
            if not name:
                continue

            content_el = elem.find("dynamic-content")
            if content_el is not None and content_el.text:
                val = content_el.text.strip()
                # Boolean conversions
                if val.lower() == "true":
                    fields[name] = True
                elif val.lower() == "false":
                    fields[name] = False
                elif val.lower() == "null":
                    fields[name] = None
                else:
                    fields[name] = val
            else:
                options = [
                    opt.text.strip()
                    for opt in elem.findall(".//option")
                    if opt.text and opt.text.strip()
                ]
                if options:
                    fields[name] = options
                else:
                    fields[name] = ""
    except Exception as err:
        logger.warning(f"Erro ao analisar XML de dynamic-elements: {err}")

    return fields


class OfferParser:
    """Parser responsible for creating normalized OfferState from Senac sources."""

    @staticmethod
    def parse_api_offer(
        xml_content: str,
        bolsa_data: Optional[Dict[str, Any]] = None,
        course_meta: Optional[Dict[str, Any]] = None,
        unit_name: Optional[str] = None,
        offer_url: Optional[str] = None,
    ) -> OfferState:
        """Constructs an OfferState from internal Senac API XML and WSE Bolsa responses."""
        fields = parse_xml_dynamic_elements(xml_content)
        course_meta = course_meta or {}

        curso = (
            course_meta.get("tituloComercial")
            or course_meta.get("titulo")
            or "Curso não informado"
        )
        unidade = unit_name or "Unidade não informada"
        codigo_oferta = str(fields.get("codigoOferta", "")).strip()

        # Turno
        periodo_raw = str(fields.get("periodoDiaOferta", "")).strip()
        horarios_all = str(fields.get("horariosAllOferta", "")).strip()
        hora_inicio = str(fields.get("horaInicioOferta", "")).strip()
        hora_fim = str(fields.get("horaFimOferta", "")).strip()
        horario_completo = horarios_all or (f"{hora_inicio} às {hora_fim}" if hora_inicio else "")
        turno = normalize_shift(periodo_raw, horario_completo)

        # Datas
        datas: List[str] = []
        dt_inicio = _format_date(fields.get("dataInicioOferta"))
        dt_fim = _format_date(fields.get("dataFimOferta"))
        dt_limite_matricula = _format_date(fields.get("dtLimiteMatricula"))
        dt_abertura_bolsa = _format_date(fields.get("dataAberturaBolsaOferta"))
        hora_abertura_bolsa = str(fields.get("horaAberturaBolsaOferta", "")).strip()

        if dt_inicio:
            datas.append(f"Início: {dt_inicio}")
        if dt_fim:
            datas.append(f"Término: {dt_fim}")
        if dt_limite_matricula:
            datas.append(f"Limite Matrícula: {dt_limite_matricula}")
        if dt_abertura_bolsa:
            msg_bolsa = f"Abertura Bolsa: {dt_abertura_bolsa}"
            if hora_abertura_bolsa:
                msg_bolsa += f" às {hora_abertura_bolsa}"
            datas.append(msg_bolsa)

        # Horários
        horarios: List[str] = []
        if horario_completo:
            horarios.append(horario_completo)

        # Inscrição / Compra
        vagas_compra = bool(fields.get("vagasParaCompraOferta", False))
        botao_compra = bool(fields.get("botaoCompraOferta", False))
        inscricao_disponivel = vagas_compra

        # Bolsa
        # Check live WSE Bolsa payload if present
        vagas_bolsa = bool(fields.get("vagasBolsaOferta", False))
        botao_bolsa = bool(fields.get("botaoBolsaOferta", False))
        lista_espera = False

        if bolsa_data and "DATA" in bolsa_data and bolsa_data["DATA"]:
            b_item = bolsa_data["DATA"][0]
            vagas_bolsa = bool(b_item.get("TEM_VAGA_BOLSA", False))
            botao_bolsa = bool(b_item.get("BOTAO_BOLSA", False))
            lista_espera = bool(b_item.get("LISTA_ESPERA", False))
            if "DATA_ABERTURA" in b_item and b_item["DATA_ABERTURA"]:
                live_dt_bolsa = _format_date(b_item["DATA_ABERTURA"])
                if live_dt_bolsa and not any("Abertura Bolsa" in d for d in datas):
                    datas.append(f"Abertura Bolsa: {live_dt_bolsa}")

        bolsa_disponivel = vagas_bolsa

        # Botões
        botoes: List[str] = []
        if inscricao_disponivel:
            botoes.append("Comprar curso")
            botoes.append("Inscrever-se")
        elif botao_compra:
            botoes.append("Registrar interesse")

        if bolsa_disponivel:
            botoes.append("Inscrever para bolsa de estudo")
        elif lista_espera:
            botoes.append("Entrar na lista de espera (bolsa)")
        elif botao_bolsa:
            botoes.append("Bolsa de estudo")

        # Textos relevantes
        texto_relevante: List[str] = []
        forma_boleto = str(fields.get("formaDePagamentoBoletoOferta", "")).strip()
        forma_cartao = str(fields.get("formaDePagamentoCartaoOferta", "")).strip()
        if forma_boleto:
            texto_relevante.append(forma_boleto)
        if forma_cartao:
            texto_relevante.append(forma_cartao)

        # Status unificado
        if inscricao_disponivel and bolsa_disponivel:
            status = "Inscrições abertas e Bolsa disponível"
        elif inscricao_disponivel:
            status = "Inscrições abertas"
        elif bolsa_disponivel:
            status = "Bolsa disponível"
        elif lista_espera:
            status = "Lista de espera disponível"
        elif botao_compra or botao_bolsa:
            status = "Sem vagas disponíveis (Aguardando abertura/Interesse)"
        else:
            status = "Indisponível"

        preco_str = None
        preco_venda = fields.get("precoVendaOferta")
        if preco_venda:
            preco_str = f"R$ {preco_venda}"

        return OfferState(
            curso=curso,
            unidade=unidade,
            turno=turno,
            status=status,
            bolsa_disponivel=bolsa_disponivel,
            inscricao_disponivel=inscricao_disponivel,
            datas=datas,
            horarios=horarios,
            botoes=botoes,
            texto_relevante=texto_relevante,
            codigo_oferta=codigo_oferta or None,
            url=offer_url,
            vagas_totais=int(fields.get("qtdeTotalVagas", 0)) if fields.get("qtdeTotalVagas") else None,
            vagas_bolsa=int(fields.get("qtdeTotalVagasPSG", 0)) if fields.get("qtdeTotalVagasPSG") else None,
            preco=preco_str,
        )

    @staticmethod
    def parse_html_offer(
        html: str,
        target_offer_id: Optional[str] = None,
        default_course: Optional[str] = None,
        default_unit: Optional[str] = None,
        offer_url: Optional[str] = None,
    ) -> OfferState:
        """Parses HTML document using BeautifulSoup and embedded JS data fallback."""
        soup = BeautifulSoup(html, "html.parser")

        # 1. Course title
        curso = default_course or "Curso não informado"
        title_tag = soup.find("h1") or soup.find("title")
        if title_tag and title_tag.text:
            raw_title = title_tag.text.strip()
            # Clean "Curso Técnico - Técnico em ... - Senac ..."
            clean_title = re.sub(r"^(?:Curso\s+Técnico\s*-\s*|\s*-\s*Senac.*$)", "", raw_title).strip()
            if clean_title:
                curso = clean_title

        # 2. Unit name
        unidade = default_unit or "Unidade não informada"
        breadcrumb = soup.find(class_=re.compile(r"breadcrumb|caminho", re.I))
        if breadcrumb and "lapa faustolo" in breadcrumb.text.lower():
            unidade = "Senac Lapa Faustolo"

        # 3. Detect embedded JSON if available
        match = re.search(r'var data = JSON\.parse\(\'({.*?})\'\)', html)
        if match:
            try:
                raw_json = match.group(1).replace(r'\"', '"').replace(r'\/', '/')
                meta = json.loads(raw_json)
                if meta.get("tituloComercial"):
                    curso = meta["tituloComercial"]
            except Exception:
                pass

        # 4. Buttons and action elements
        botoes: List[str] = []
        inscricao_disponivel = False
        bolsa_disponivel = False

        buttons = soup.find_all(["button", "a"], class_=re.compile(r"btn|button|cta", re.I))
        for btn in buttons:
            txt = btn.get_text(strip=True)
            if not txt:
                continue
            txt_lower = txt.lower()
            if any(term in txt_lower for term in ["inscreva", "comprar", "matrícula", "matricula"]):
                botoes.append(txt)
                if not btn.has_attr("disabled"):
                    inscricao_disponivel = True
            elif "bolsa" in txt_lower:
                botoes.append(txt)
                if "disponível" in txt_lower or "inscrever" in txt_lower:
                    bolsa_disponivel = True
            elif "interesse" in txt_lower:
                botoes.append(txt)

        # 5. Look for specific badge tags
        texto_relevante: List[str] = []
        tags = soup.find_all(class_=re.compile(r"tag|badge|alerta", re.I))
        for t in tags:
            tag_text = t.get_text(strip=True)
            if tag_text and len(tag_text) < 150:
                texto_relevante.append(tag_text)
                if "turmas disponíveis" in tag_text.lower():
                    inscricao_disponivel = True
                if "bolsas de estudo" in tag_text.lower() and not t.has_attr("d-none"):
                    bolsa_disponivel = True

        # 6. Horários & Turno
        horarios: List[str] = []
        turno = "Não informado"
        for text_elem in soup.find_all(["p", "span", "div"], string=re.compile(r"(?:noturno|manhã|manha|tarde|\d{1,2}h(?::\d{2})?\s*às\s*\d{1,2}h|\d{1,2}:\d{2}\s*às\s*\d{1,2}:\d{2})", re.I)):
            s = text_elem.get_text(strip=True)
            if len(s) < 100:
                horarios.append(s)
                shift_cand = normalize_shift(None, s)
                if shift_cand != "Não informado":
                    turno = shift_cand

        if turno == "Não informado" and not horarios:
            turno = "Noturno"

        # Dates
        datas: List[str] = []
        for date_elem in soup.find_all(string=re.compile(r"\b\d{2}/\d{2}/\d{4}\b")):
            parent_text = date_elem.parent.get_text(strip=True)
            if len(parent_text) < 100 and parent_text not in datas:
                datas.append(parent_text)

        status = "Indisponível"
        if inscricao_disponivel and bolsa_disponivel:
            status = "Inscrições abertas e Bolsa disponível"
        elif inscricao_disponivel:
            status = "Inscrições abertas"
        elif bolsa_disponivel:
            status = "Bolsa disponível"
        elif any("interesse" in b.lower() for b in botoes):
            status = "Sem inscrições disponíveis (Registro de interesse)"

        return OfferState(
            curso=curso,
            unidade=unidade,
            turno=turno,
            status=status,
            bolsa_disponivel=bolsa_disponivel,
            inscricao_disponivel=inscricao_disponivel,
            datas=datas,
            horarios=horarios,
            botoes=list(dict.fromkeys(botoes)),
            texto_relevante=list(dict.fromkeys(texto_relevante))[:10],
            codigo_oferta=target_offer_id,
            url=offer_url,
        )
