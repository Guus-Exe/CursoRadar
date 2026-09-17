"""Senac São Paulo concrete EducationProvider implementation."""

from typing import List, Optional
import httpx
from app.config import Settings, get_settings
from app.models import DiscoveredOffer, OfferState
from app.providers.base import CourseData, EducationProvider, LocationData
from app.scrapers.senac import SenacScraper
from app.utils.logger import logger


class SenacSPProvider(EducationProvider):
    """Education provider implementation for Senac São Paulo."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.settings = settings or get_settings()
        self.scraper = SenacScraper(client=client)

    @property
    def institution_slug(self) -> str:
        return "senac-sp"

    @property
    def institution_name(self) -> str:
        return "Senac São Paulo"

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
        """Searches Senac course catalog."""
        # Seeded/verified courses with known article IDs
        known_courses = [
            CourseData(
                name="Técnico em Modelagem do Vestuário",
                slug="curso-tecnico-em-modelagem-do-vestuario",
                category="cursos-tecnicos",
                external_id="52620802",
            ),
            CourseData(
                name="Técnico em Informática",
                slug="curso-tecnico-em-informatica",
                category="cursos-tecnicos",
                external_id="52620810",
            ),
            CourseData(
                name="Técnico em Administração",
                slug="curso-tecnico-em-administracao",
                category="cursos-tecnicos",
                external_id="52620820",
            ),
            CourseData(
                name="Técnico em Enfermagem",
                slug="curso-tecnico-em-enfermagem",
                category="cursos-tecnicos",
                external_id="52620830",
            ),
            CourseData(
                name="Técnico em Design de Interiores",
                slug="curso-tecnico-em-design-de-interiores",
                category="cursos-tecnicos",
                external_id="52620840",
            ),
        ]

        q = query.strip().lower()
        if not q:
            return known_courses

        return [
            c for c in known_courses
            if q in c.name.lower() or q in c.slug.lower()
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
