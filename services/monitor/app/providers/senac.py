from typing import Any, List, Optional
import httpx
from app.config import Settings, get_settings
from app.models import DiscoveredOffer, OfferState
from app.providers.base import (
    CourseData,
    EducationProvider,
    LocationData,
    NormalizedOffer,
    ProviderSearchResult,
    SearchStatus,
)
from app.scrapers.senac import SenacScraper, rank_best_course
from app.utils.logger import logger


class SenacSPProvider(EducationProvider):
    """Education provider implementation for Senac São Paulo."""

    enabled: bool = True

    def __init__(
        self,
        settings: Optional[Settings] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.settings = settings or get_settings()
        self.scraper = SenacScraper(client=client)

    @property
    def slug(self) -> str:
        return "senac_sp"

    @property
    def name(self) -> str:
        return "Senac São Paulo"

    @property
    def institution_slug(self) -> str:
        return "senac-sp"

    @property
    def institution_name(self) -> str:
        return "Senac São Paulo"

    def healthcheck(self) -> bool:
        return True

    @staticmethod
    def _get_seeded_courses() -> List[CourseData]:
        """Seeded verified courses for offline fallback and tests."""
        return [
            CourseData(
                name="Técnico em Modelagem do Vestuário",
                slug="cursos-tecnicos/curso-tecnico-em-modelagem-do-vestuario",
                category="cursos-tecnicos",
                external_id="52620802",
            ),
            CourseData(
                name="Técnico em Informática",
                slug="cursos-tecnicos/curso-tecnico-em-informatica",
                category="cursos-tecnicos",
                external_id="52620810",
            ),
            CourseData(
                name="Técnico em Administração",
                slug="cursos-tecnicos/curso-tecnico-em-administracao",
                category="cursos-tecnicos",
                external_id="52620820",
            ),
            CourseData(
                name="Técnico em Enfermagem",
                slug="cursos-tecnicos/curso-tecnico-em-enfermagem",
                category="cursos-tecnicos",
                external_id="52620830",
            ),
            CourseData(
                name="Técnico em Design de Interiores",
                slug="cursos-tecnicos/curso-tecnico-em-design-de-interiores",
                category="cursos-tecnicos",
                external_id="52620840",
            ),
        ]

    async def search_offers_structured(
        self,
        query: str = "",
        unit_filter: Optional[str] = None,
        **kwargs: Any,
    ) -> ProviderSearchResult:
        """Executes full search and returns structured diagnostic outcome alongside normalized offers."""
        q_clean = query.strip()
        if not q_clean:
            return ProviderSearchResult(
                provider_slug=self.slug,
                search_query=query,
                status=SearchStatus.COURSE_NOT_FOUND,
                message="Termo de busca vazio.",
            )

        try:
            candidates = await self.scraper.search_courses_api(q_clean)
        except Exception as err:
            logger.error(f"[{self.slug}] Erro ao buscar cursos para '{q_clean}': {err}")
            return ProviderSearchResult(
                provider_slug=self.slug,
                search_query=query,
                status=SearchStatus.ERROR,
                message=f"Falha técnica ao consultar o portal Senac SP: {err}",
                offers=[],
                diagnostic={"error": str(err)},
            )

        if not candidates:
            return ProviderSearchResult(
                provider_slug=self.slug,
                search_query=query,
                status=SearchStatus.COURSE_NOT_FOUND,
                message="Curso não encontrado no catálogo do Senac SP.",
            )

        best_course, score = rank_best_course(q_clean, candidates)
        if not best_course or score < 0.4:
            logger.info(
                f"[{self.slug}] Nenhum candidato com relevância satisfatória para '{q_clean}' "
                f"(melhor: '{best_course.name if best_course else 'Nenhum'}' com score {score:.2f})."
            )
            return ProviderSearchResult(
                provider_slug=self.slug,
                search_query=query,
                status=SearchStatus.COURSE_NOT_FOUND,
                message="Nenhum curso correspondente encontrado com relevância suficiente.",
            )

        course_full_url = f"https://www.sp.senac.br/{best_course.slug.lstrip('/')}"

        # Limitation: explicitly handle unsupported course types
        if best_course.category != "cursos-tecnicos":
            logger.info(f"[{self.slug}] Curso '{best_course.name}' categoria '{best_course.category}' não suportado nesta etapa.")
            return ProviderSearchResult(
                provider_slug=self.slug,
                search_query=query,
                status=SearchStatus.UNSUPPORTED_COURSE_TYPE,
                course_name=best_course.name,
                course_url=course_full_url,
                article_id=best_course.external_id,
                category=best_course.category,
                message=(
                    f"Curso '{best_course.name}' é do tipo '{best_course.category}'. "
                    f"Nesta etapa, o monitoramento suporta exclusivamente Cursos Técnicos."
                ),
                offers=[],
            )

        # Technical course: extract real classes
        try:
            meta, offers_states = await self.scraper.fetch_technical_course_offers(best_course, unit_filter=unit_filter)
        except Exception as err:
            logger.error(f"[{self.slug}] Erro ao extrair turmas do curso técnico '{best_course.name}': {err}")
            return ProviderSearchResult(
                provider_slug=self.slug,
                search_query=query,
                status=SearchStatus.ERROR,
                course_name=best_course.name,
                course_url=course_full_url,
                article_id=best_course.external_id,
                category="cursos-tecnicos",
                message=f"Erro ao extrair turmas técnicas: {err}",
            )

        units_names = [u.get("nome", "") for u in meta.get("unidades", []) if u.get("nome")]
        codigo_ft = str(meta.get("codigoFT", ""))
        article_id = str(meta.get("articleId") or best_course.external_id or "")

        if not offers_states:
            return ProviderSearchResult(
                provider_slug=self.slug,
                search_query=query,
                status=SearchStatus.NO_CLASSES_FOUND,
                course_name=best_course.name,
                course_url=course_full_url,
                article_id=article_id,
                codigo_ft=codigo_ft,
                category="cursos-tecnicos",
                units_found=units_names,
                classes_count=0,
                available_classes_count=0,
                message=f"Curso técnico '{best_course.name}' encontrado, porém não há turmas cadastradas no momento.",
                offers=[],
            )

        normalized_offers: List[NormalizedOffer] = []
        for st in offers_states:
            normalized_offers.append(
                NormalizedOffer(
                    provider_slug=self.slug,
                    external_id=st.codigo_oferta,
                    title=st.curso,
                    institution_name=self.name,
                    campus_or_unit=st.unidade,
                    city=st.unidade.replace("Senac ", "").strip() if st.unidade else None,
                    modality="presencial",
                    shift=st.turno,
                    source_url=st.url or course_full_url,
                    status=st.status,
                    bolsa_disponivel=st.bolsa_disponivel,
                    inscricao_disponivel=st.inscricao_disponivel,
                    raw_data={
                        "codigo_oferta": st.codigo_oferta,
                        "horarios": st.horarios,
                        "datas": st.datas,
                        "botoes": st.botoes,
                        "raw_status": st.status,
                    },
                )
            )

        available_count = len([o for o in normalized_offers if o.inscricao_disponivel or o.bolsa_disponivel])
        status = (
            SearchStatus.AVAILABLE_OFFERS_FOUND
            if available_count > 0
            else SearchStatus.CLASSES_FOUND_NO_AVAILABILITY
        )

        msg = (
            f"{available_count} vaga(s) aberta(s) de {len(normalized_offers)} turma(s) encontrada(s)."
            if available_count > 0
            else f"{len(normalized_offers)} turma(s) encontrada(s), mas todas sem vagas no momento."
        )

        return ProviderSearchResult(
            provider_slug=self.slug,
            search_query=query,
            status=status,
            course_name=best_course.name,
            course_url=course_full_url,
            article_id=article_id,
            codigo_ft=codigo_ft,
            category="cursos-tecnicos",
            units_found=units_names,
            classes_count=len(normalized_offers),
            available_classes_count=available_count,
            raw_status_list=[o.status for o in normalized_offers],
            offers=normalized_offers,
            message=msg,
        )

    async def search_offers(self, query: str = "", **kwargs: Any) -> List[NormalizedOffer]:
        """Searches Senac offers and normalizes them into NormalizedOffer."""
        res = await self.search_offers_structured(query, **kwargs)
        return res.offers

    async def get_locations(self) -> List[LocationData]:
        """Returns catalog of known Senac SP units."""
        # Built-in units with their respective Liferay categoryIds
        units = [
            LocationData(
                name="Senac Lapa Faustolo",
                slug="senac-lapa-faustolo",
                city="São Paulo",
                state="SP",
                external_id="40814",
            ),
            LocationData(
                name="Senac Lapa Tito",
                slug="senac-lapa-tito",
                city="São Paulo",
                state="SP",
                external_id="40815",
            ),
            LocationData(
                name="Senac Tiradentes",
                slug="senac-tiradentes",
                city="São Paulo",
                state="SP",
                external_id="40816",
            ),
            LocationData(
                name="Senac Campinas",
                slug="senac-campinas",
                city="Campinas",
                state="SP",
                external_id="40820",
            ),
            LocationData(
                name="Senac Santos",
                slug="senac-santos",
                city="Santos",
                state="SP",
                external_id="40825",
            ),
            LocationData(
                name="Senac São José dos Campos",
                slug="senac-sao-jose-dos-campos",
                city="São José dos Campos",
                state="SP",
                external_id="40830",
            ),
        ]
        return units

    async def search_courses(self, query: str) -> List[CourseData]:
        """Searches Senac course catalog dynamically via keywords API."""
        q = query.strip()
        if not q:
            return self._get_seeded_courses()

        try:
            results = await self.scraper.search_courses_api(q)
            if results:
                return results
        except Exception as err:
            logger.warning(f"Erro ao consultar API de busca do Senac para '{q}': {err}")

        # Fallback to seeded courses if offline / network error / test environment
        q_norm = q.lower()
        return [
            c for c in self._get_seeded_courses()
            if q_norm in c.name.lower() or q_norm in c.slug.lower()
        ]

    async def discover_offers(
        self,
        course_name: str,
        unit_name: str,
        shift: Optional[str] = None,
    ) -> List[DiscoveredOffer]:
        """Discovers current and future offers matching course, unit, and shift."""
        return await self.scraper.discover_new_offers(
            course_name=course_name,
            unit_name=unit_name,
            shift=shift,
        )

    async def get_offer_state(self, url_or_id: str) -> OfferState:
        """Fetches and normalizes the current availability state of an offer."""
        return await self.scraper.get_offer_state(url_or_id)
