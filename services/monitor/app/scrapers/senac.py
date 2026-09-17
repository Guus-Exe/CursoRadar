"""Senac São Paulo web scraper and API client."""

import asyncio
from datetime import datetime
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse
import httpx
from app.config import get_settings
from app.models import DiscoveredOffer, OfferState
from app.scrapers.base import BaseScraper
from app.scrapers.offer_parser import OfferParser, normalize_shift
from app.utils.logger import logger


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

    async def get_offer_state(self, url_or_id: str) -> OfferState:
        """Retrieves and normalizes offer state from URL or offer ID."""
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

        # 1. Fetch course page to get metadata and Liferay tokens
        logger.info(f"Carregando página do curso: {target_url}")
        html = await self.fetch_page_html(target_url)

        # 2. Extract embedded course data from HTML
        article_id = "52620802"
        codigo_ft = "21464"
        data_efetiva = "2023-01-01"
        category_id_unidade = "40814"  # Default Lapa Faustolo
        unidade_nome = self.settings.unit_name
        course_meta = {"tituloComercial": self.settings.course_name}

        match = re.search(r'var data = JSON\.parse\(\'({.*?})\'\)', html)
        if match:
            try:
                raw_json = match.group(1).replace(r'\"', '"').replace(r'\/', '/')
                extracted_meta = json.loads(raw_json)
                course_meta.update(extracted_meta)
                article_id = str(extracted_meta.get("articleId", article_id))
                codigo_ft = str(extracted_meta.get("codigoFT", codigo_ft))
                data_efetiva = str(extracted_meta.get("dataEfetivaSTR", data_efetiva))

                # Identify unit categoryId
                for u in extracted_meta.get("unidades", []):
                    u_name = u.get("nome", "").lower()
                    if "faustolo" in u_name or "lapa" in u_name:
                        category_id_unidade = str(u.get("categoryId", category_id_unidade))
                        unidade_nome = u.get("nome", unidade_nome)
                        break
            except Exception as err:
                logger.warning(f"Erro ao analisar metadados embutidos do curso: {err}")

        # 3. Query internal ofertasPorCategoryIds service
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
                # Find matching target offer if specified, otherwise take first
                matching_item = None
                for item in raw_offers:
                    content_xml = item.get("content", "")
                    if target_offer_id and target_offer_id in content_xml:
                        matching_item = item
                        break

                if not matching_item:
                    matching_item = raw_offers[0]

                content_xml = matching_item.get("content", "")
                # Query real-time bolsa status
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

        # 4. Fallback parser on HTML page
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
        """Searches Senac portal for new offers of the given course and unit."""
        logger.info(f"Iniciando busca de novas ofertas para '{course_name}' na unidade '{unit_name}'...")
        query = course_name.replace(" ", "%20")
        search_url = (
            f"https://www.sp.senac.br/o/senacsearch/keywords-v2/curso/"
            f"{SENAC_COMPANY_ID}/{SENAC_GROUP_ID}/modelagem/0/30"
        )

        offers_found: List[DiscoveredOffer] = []

        try:
            resp = await self._request_with_retry(
                "GET",
                search_url,
                headers={"Accept": "application/json, text/plain, */*"},
            )
            data = resp.json()
            cursos = data.get("cursos", [])

            matching_course = None
            for c in cursos:
                url_title = c.get("url", "")
                titles = c.get("title_pt_BR", [])
                if "modelagem-do-vestuario" in url_title or any("modelagem do vestuário" in t.lower() for t in titles):
                    matching_course = c
                    break

            if not matching_course:
                logger.info("Curso não encontrado no resultado de busca por palavras-chave.")
                return offers_found

            codigo_ft = matching_course.get("codigoFT_pt_BR", "21464")
            data_efetiva = matching_course.get("dataEfetivaFT", "2023-01-01")
            article_ids = matching_course.get("articleId", ["52620802"])
            article_id = article_ids[0] if article_ids else "52620802"
            course_rel_url = matching_course.get("url", "cursos-tecnicos/curso-tecnico-em-modelagem-do-vestuario")

            # Lapa Faustolo category ID = 40814
            category_id = "40814"
            api_url = f"https://www.sp.senac.br/o/senac-oferta-services/ofertasPorCategoryIds/{SENAC_GROUP_ID}"
            params = {
                "codigoFTOferta": codigo_ft,
                "dataEfetivaOferta": data_efetiva,
                "categoryIds": category_id,
                "inscricaoAberta": "false",
                "bolsaAberta": "false",
                "cursoArticleId": article_id,
                "considerarDataBolsaFutura": "true",
                "start": "-1",
                "end": "-1",
            }

            ofertas_resp = await self._request_with_retry("GET", api_url, params=params)
            ofertas_data = ofertas_resp.json()

            for item in ofertas_data:
                content_xml = item.get("content", "")
                parsed = OfferParser.parse_api_offer(
                    xml_content=content_xml,
                    course_meta={"tituloComercial": course_name},
                    unit_name=unit_name,
                )

                # Filter by shift if provided
                if shift:
                    if shift.lower() not in parsed.turno.lower():
                        continue

                offer_url = (
                    f"https://www.sp.senac.br/senac-lapa-faustolo/{course_rel_url}"
                    f"?bolsa=true&oferta={parsed.codigo_oferta}"
                )

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

            logger.info(f"Busca concluída: {len(offers_found)} ofertas encontradas para {unit_name}.")
        except Exception as err:
            logger.error(f"Erro ao buscar novas ofertas no Senac: {err}")

        return offers_found
