"""Senac São Paulo web scraper and API client."""

import asyncio
from datetime import datetime
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote, urlencode, urlparse
import httpx
from app.config import get_settings
from app.models import DiscoveredOffer, OfferState
from app.providers.base import CourseData
from app.scrapers.base import BaseScraper
from app.scrapers.offer_parser import OfferParser, normalize_shift
from app.utils.logger import logger


def rank_best_course(query: str, candidates: List[CourseData]) -> Tuple[Optional[CourseData], float]:
    """Ranks and selects the most relevant course match for the given query."""
    if not candidates:
        return None, 0.0

    from app.matching import normalize_text

    q_norm = normalize_text(query)
    q_words = set(q_norm.split())
    stopwords = {"em", "de", "do", "da", "para", "e", "com", "no", "na"}
    key_q = q_words - stopwords
    if not key_q:
        key_q = q_words

    best_candidate: Optional[CourseData] = None
    best_score = -1.0

    for c in candidates:
        t_norm = normalize_text(c.name)
        s_norm = normalize_text(c.slug.replace("-", " ").replace("/", " "))

        if q_norm == t_norm or q_norm == s_norm:
            return c, 1.0

        t_words = set(t_norm.split()) - stopwords
        intersection = key_q.intersection(t_words)
        if not intersection:
            score = 0.0
        else:
            overlap = len(intersection) / len(key_q)
            score = overlap * 0.75

            if q_norm in t_norm or t_norm in q_norm:
                score += 0.15

            # Priority bonus for technical course
            if c.category == "cursos-tecnicos" or "tecnico" in t_norm or "cursos-tecnicos" in c.slug:
                score += 0.20

            # Penalty for extraneous words not in the query
            extra_words = len(t_words - key_q)
            score -= extra_words * 0.05

        if score > best_score:
            best_score = score
            best_candidate = c

    if best_score < 0.40:
        return None, max(best_score, 0.0)

    return best_candidate, max(best_score, 0.0)


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}

SENAC_COMPANY_ID = "20102"
SENAC_GROUP_ID = "20125"


class SenacScraper(BaseScraper):
    """Scraper that interacts with Senac SP course pages and internal APIs."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.settings = get_settings()
        self._external_client = client
        self.timeout = httpx.Timeout(self.settings.request_timeout_seconds)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._external_client is not None:
            return self._external_client
        return httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=self.timeout,
            follow_redirects=True,
        )

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        max_retries: Optional[int] = None,
    ) -> httpx.Response:
        """Executes HTTP request with exponential backoff on transient errors."""
        retries = max_retries if max_retries is not None else self.settings.max_retries
        client = await self._get_client()
        req_headers = dict(DEFAULT_HEADERS)
        if headers:
            req_headers.update(headers)

        last_exception = None
        for attempt in range(1, retries + 1):
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=req_headers,
                )
                # Handle rate-limiting or server errors
                if response.status_code in (429, 500, 502, 503, 504):
                    wait_time = 2**attempt
                    logger.warning(
                        f"HTTP {response.status_code} para {url}. "
                        f"Tentativa {attempt}/{retries}. Aguardando {wait_time}s..."
                    )
                    if attempt < retries:
                        await asyncio.sleep(wait_time)
                        continue
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.NetworkError) as err:
                last_exception = err
                wait_time = 2**attempt
                logger.warning(
                    f"Falha de rede/timeout ao acessar {url}: {err}. "
                    f"Tentativa {attempt}/{retries}. Aguardando {wait_time}s..."
                )
                if attempt < retries:
                    await asyncio.sleep(wait_time)
            except httpx.HTTPStatusError as err:
                last_exception = err
                if err.response.status_code in (403, 404):
                    logger.error(f"Erro HTTP {err.response.status_code} ao acessar {url}")
                    raise
                if attempt < retries:
                    await asyncio.sleep(2**attempt)
                else:
                    raise

        raise last_exception or RuntimeError(f"Falha na requisição para {url}")

    async def fetch_page_html(self, url: str) -> str:
        """Downloads the course HTML page."""
        response = await self._request_with_retry("GET", url)
        return response.text

    async def fetch_live_bolsa_data(self, offer_id: str, destino_bolsa: str = "2") -> Optional[Dict[str, Any]]:
        """Queries Senac's official real-time scholarship verification service (wse-bolsas)."""
        if destino_bolsa == "1":
            url = f"https://wse.sp.senac.br/rest/wss/cursos/bolsa/v1/?COD_EVENTO={offer_id}"
        else:
            url = f"https://wse-bolsas.sp.senac.br/api/cursos/bolsa/v1/{offer_id}"

        headers = {
            "Accept": "application/json, text/plain, */*",
        }
        if self.settings.senac_bolsa_auth:
            headers["Authorization"] = self.settings.senac_bolsa_auth

        try:
            response = await self._request_with_retry("GET", url, headers=headers, max_retries=2)
            return response.json()
        except Exception as err:
            logger.warning(f"Não foi possível consultar wse-bolsas para oferta {offer_id}: {err}")
            return None

    async def search_courses_api(self, query: str) -> List[CourseData]:
        """Queries Senac SP keywords search API and normalizes found courses."""
        q_clean = query.strip()
        if not q_clean:
            return []

        search_url = (
            f"https://www.sp.senac.br/o/senacsearch/keywords-v2/curso/"
            f"{SENAC_COMPANY_ID}/{SENAC_GROUP_ID}/{quote(q_clean)}/0/30"
        )
        logger.info(f"Consultando catálogo do Senac SP via API para query '{q_clean}'...")
        try:
            resp = await self._request_with_retry(
                "GET",
                search_url,
                headers={"Accept": "application/json, text/plain, */*"},
            )
            data = resp.json()
            cursos = data.get("cursos", [])
            logger.info(f"API do Senac SP retornou {len(cursos)} resultado(s) bruto(s) para '{q_clean}'.")
        except Exception as err:
            logger.error(f"Falha ao consultar API de palavras-chave do Senac para '{q_clean}': {err}")
            raise

        courses: List[CourseData] = []
        for c in cursos:
            t_raw = c.get("title_pt_BR")
            if isinstance(t_raw, list) and t_raw:
                title = t_raw[0]
            else:
                title = str(t_raw or "")

            rel_url = str(c.get("url") or "").strip().lstrip("/")
            art_raw = c.get("articleId")
            if isinstance(art_raw, list) and art_raw:
                article_id = str(art_raw[0])
            else:
                article_id = str(art_raw or "")

            codigo_ft = str(c.get("codigoFT_pt_BR") or c.get("codigoFT") or "")
            category = "cursos-tecnicos" if rel_url.startswith("cursos-tecnicos/") else (rel_url.split("/")[0] if "/" in rel_url else "outro")

            courses.append(
                CourseData(
                    id=article_id or None,
                    name=title,
                    slug=rel_url,
                    category=category,
                    external_id=article_id or None,
                )
            )

        return courses

    async def fetch_technical_course_offers(
        self,
        course_data: CourseData,
        unit_filter: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], List[OfferState]]:
        """Extracts technical course metadata and all class offers without silent fallbacks."""
        course_full_url = f"https://www.sp.senac.br/{course_data.slug.lstrip('/')}"
        logger.info(f"Carregando página do curso técnico: {course_full_url}")

        html = await self.fetch_page_html(course_full_url)
        match = re.search(r'var data = JSON\.parse\(\'({.*?})\'\)', html)
        if not match:
            logger.error(f"Página '{course_full_url}' não contém bloco de dados 'var data = JSON.parse'. Fallback para Modelagem desabilitado.")
            raise ValueError(f"Metadados técnicos 'var data' não encontrados na página {course_full_url}.")

        raw_json = match.group(1).replace(r'\"', '"').replace(r'\/', '/')
        meta = json.loads(raw_json)

        article_id = str(meta.get("articleId") or course_data.external_id or "").strip()
        codigo_ft = str(meta.get("codigoFT") or "").strip()
        data_efetiva = str(meta.get("dataEfetivaSTR") or "2022-01-01").strip()
        unidades = meta.get("unidades", [])

        if not article_id or not codigo_ft:
            raise ValueError(f"Metadados incompletos na página {course_full_url}: articleId={article_id}, codigoFT={codigo_ft}")

        # Build categoryId to unit name map
        unit_map: Dict[str, str] = {}
        for u in unidades:
            c_id = str(u.get("categoryId") or "").strip()
            u_name = u.get("nome") or "Senac SP"
            if c_id:
                unit_map[c_id] = u_name

        # Filter units if filter provided
        target_cat_ids = []
        if unit_filter and unit_filter.lower() != "qualquer":
            uf_clean = unit_filter.lower().strip()
            for c_id, u_name in unit_map.items():
                if uf_clean in u_name.lower():
                    target_cat_ids.append(c_id)
        if not target_cat_ids:
            target_cat_ids = list(unit_map.keys())

        if not target_cat_ids:
            logger.info(f"Nenhuma unidade com categoryId válida para o curso {course_data.name}.")
            return meta, []

        cat_ids_param = ",".join(target_cat_ids)
        api_url = f"https://www.sp.senac.br/o/senac-oferta-services/ofertasPorCategoryIds/{SENAC_GROUP_ID}"
        params = {
            "codigoFTOferta": codigo_ft,
            "dataEfetivaOferta": data_efetiva,
            "categoryIds": cat_ids_param,
            "inscricaoAberta": "false",
            "bolsaAberta": "false",
            "cursoArticleId": article_id,
            "considerarDataBolsaFutura": "true",
            "start": "-1",
            "end": "-1",
        }

        try:
            resp = await self._request_with_retry(
                "GET",
                api_url,
                params=params,
                headers={"Referer": course_full_url, "Accept": "application/json, text/plain, */*"},
            )
            raw_offers = resp.json()
        except Exception as err:
            logger.error(f"Erro ao consultar ofertasPorCategoryIds para {course_data.name}: {err}")
            raise

        offers_states: List[OfferState] = []
        if isinstance(raw_offers, list):
            for item in raw_offers:
                content_xml = item.get("content", "")
                unit_cat = str(item.get("unidadeCategoryIds") or "").strip()
                unit_name = unit_map.get(unit_cat, "Senac São Paulo")

                state = OfferParser.parse_api_offer(
                    xml_content=content_xml,
                    course_meta=meta,
                    unit_name=unit_name,
                    offer_url=course_full_url,
                )
                if state.codigo_oferta:
                    state.url = f"{course_full_url}?oferta={state.codigo_oferta}"
                offers_states.append(state)

        logger.info(f"Extraídas {len(offers_states)} oferta(s) para {course_data.name} via API interna.")
        return meta, offers_states

    async def get_offer_state(self, url_or_id: str) -> OfferState:
        """Retrieves and normalizes offer state from URL or offer ID without silent fallback."""
        target_url = url_or_id
        target_offer_id = self.settings.target_offer_id

        if url_or_id.startswith("http://") or url_or_id.startswith("https://"):
            parsed_url = urlparse(url_or_id)
            query_params = parse_qs(parsed_url.query)
            if "oferta" in query_params:
                target_offer_id = query_params["oferta"][0]
        else:
            target_offer_id = url_or_id
            target_url = self.settings.senac_offer_url

        logger.info(f"Carregando página do curso: {target_url}")
        html = await self.fetch_page_html(target_url)

        match = re.search(r'var data = JSON\.parse\(\'({.*?})\'\)', html)
        if match:
            raw_json = match.group(1).replace(r'\"', '"').replace(r'\/', '/')
            extracted_meta = json.loads(raw_json)
            article_id = str(extracted_meta.get("articleId", "")).strip()
            codigo_ft = str(extracted_meta.get("codigoFT", "")).strip()
            data_efetiva = str(extracted_meta.get("dataEfetivaSTR", "2023-01-01")).strip()
            course_meta = extracted_meta
            unidade_nome = self.settings.unit_name
            category_id_unidade = ""

            for u in extracted_meta.get("unidades", []):
                u_name = u.get("nome", "").lower()
                if self.settings.unit_name.lower() in u_name:
                    category_id_unidade = str(u.get("categoryId", ""))
                    unidade_nome = u.get("nome", unidade_nome)
                    break
            if not category_id_unidade and extracted_meta.get("unidades"):
                first_u = extracted_meta["unidades"][0]
                category_id_unidade = str(first_u.get("categoryId", ""))
                unidade_nome = first_u.get("nome", unidade_nome)
        else:
            m_art = re.search(r'<input[^>]+name="articleId"[^>]+value="([^"]+)"', html)
            m_ft = re.search(r'<input[^>]+name="codigoFT"[^>]+value="([^"]+)"', html)
            if m_art and m_ft:
                article_id = m_art.group(1).strip()
                codigo_ft = m_ft.group(1).strip()
                data_efetiva = "2022-01-01"
                category_id_unidade = ""
                unidade_nome = self.settings.unit_name
                course_meta = {"tituloComercial": self.settings.course_name}
            else:
                logger.warning(f"Metadados técnicos dinâmicos ausentes em {target_url}. Utilizando parser HTML.")
                return OfferParser.parse_html_offer(
                    html=html,
                    target_offer_id=target_offer_id,
                    default_course=self.settings.course_name,
                    default_unit=self.settings.unit_name,
                    offer_url=target_url,
                )

        if not article_id or not codigo_ft:
            return OfferParser.parse_html_offer(
                html=html,
                target_offer_id=target_offer_id,
                default_course=self.settings.course_name,
                default_unit=self.settings.unit_name,
                offer_url=target_url,
            )

        api_url = f"https://www.sp.senac.br/o/senac-oferta-services/ofertasPorCategoryIds/{SENAC_GROUP_ID}"
        params = {
            "codigoFTOferta": codigo_ft,
            "dataEfetivaOferta": data_efetiva,
            "categoryIds": category_id_unidade,
            "inscricaoAberta": "false",
            "bolsaAberta": "false",
            "cursoArticleId": article_id,
            "considerarDataBolsaFutura": "true",
            "start": "-1",
            "end": "-1",
        }

        try:
            resp = await self._request_with_retry(
                "GET",
                api_url,
                params=params,
                headers={"Referer": target_url, "Accept": "application/json, text/plain, */*"},
            )
            raw_offers = resp.json()
            if isinstance(raw_offers, list) and len(raw_offers) > 0:
                matching_item = None
                for item in raw_offers:
                    content_xml = item.get("content", "")
                    if target_offer_id and target_offer_id in content_xml:
                        matching_item = item
                        break

                if not matching_item:
                    matching_item = raw_offers[0]

                content_xml = matching_item.get("content", "")
                bolsa_data = None
                if target_offer_id:
                    bolsa_data = await self.fetch_live_bolsa_data(target_offer_id)

                state = OfferParser.parse_api_offer(
                    xml_content=content_xml,
                    bolsa_data=bolsa_data,
                    course_meta=course_meta,
                    unit_name=unidade_nome,
                    offer_url=target_url,
                )
                logger.info(f"Oferta {state.codigo_oferta} analisada com sucesso via API do Senac.")
                return state
        except Exception as err:
            logger.warning(f"Consulta à API interna de ofertas falhou ({err}). Utilizando parser de HTML...")

        state = OfferParser.parse_html_offer(
            html=html,
            target_offer_id=target_offer_id,
            default_course=self.settings.course_name,
            default_unit=self.settings.unit_name,
            offer_url=target_url,
        )
        logger.info(f"Oferta analisada com sucesso via parser HTML (status: {state.status}).")
        return state

    async def discover_new_offers(
        self,
        course_name: str,
        unit_name: str,
        shift: Optional[str] = None,
    ) -> List[DiscoveredOffer]:
        """Searches Senac portal for new offers of the given course and unit dynamically."""
        logger.info(f"Iniciando busca dinâmica de novas ofertas para '{course_name}' na unidade '{unit_name}'...")
        offers_found: List[DiscoveredOffer] = []

        try:
            candidates = await self.search_courses_api(course_name)
            if not candidates:
                logger.info(f"Nenhum curso retornado pela API de busca para '{course_name}'.")
                return offers_found

            best_course, score = rank_best_course(course_name, candidates)
            if not best_course or score < 0.4:
                logger.info(f"Nenhum curso com relevância suficiente para '{course_name}' (score: {score:.2f}).")
                return offers_found

            if best_course.category != "cursos-tecnicos":
                logger.info(f"Curso '{best_course.name}' é da categoria '{best_course.category}'. Descoberta suporta apenas cursos técnicos.")
                return offers_found

            _, offers_states = await self.fetch_technical_course_offers(best_course, unit_filter=unit_name)

            for parsed in offers_states:
                if shift and shift.lower() != "qualquer":
                    if shift.lower() not in parsed.turno.lower():
                        continue

                offer_url = parsed.url or f"https://www.sp.senac.br/{best_course.slug}?oferta={parsed.codigo_oferta}"
                discovered = DiscoveredOffer(
                    codigo_oferta=parsed.codigo_oferta or "desconhecida",
                    curso=parsed.curso,
                    unidade=parsed.unidade,
                    turno=parsed.turno,
                    url=offer_url,
                    data_inicio=parsed.datas[0] if parsed.datas else None,
                    horario=parsed.horarios[0] if parsed.horarios else None,
                    vagas_disponiveis=parsed.inscricao_disponivel,
                    bolsa_disponivel=parsed.bolsa_disponivel,
                    descoberto_em=datetime.now(),
                )
                offers_found.append(discovered)

            logger.info(f"Busca de descoberta concluída: {len(offers_found)} ofertas encontradas para {course_name} em {unit_name}.")
        except Exception as err:
            logger.error(f"Erro ao buscar novas ofertas no Senac para '{course_name}': {err}")

        return offers_found
