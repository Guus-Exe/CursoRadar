"""Abstract base EducationProvider interface and normalized models for educational institutions."""

from abc import ABC, abstractmethod
from enum import Enum
import hashlib
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from app.models import DiscoveredOffer, OfferState


class LocationData(BaseModel):
    """Normalized campus or unit of an educational institution."""

    id: Optional[str] = None
    name: str
    slug: str
    city: str
    state: str = "SP"
    external_id: Optional[str] = None


class CourseData(BaseModel):
    """Normalized course metadata."""

    id: Optional[str] = None
    name: str
    slug: str
    category: str = "cursos-tecnicos"
    external_id: Optional[str] = None


class NormalizedOffer(BaseModel):
    """Universal normalized educational offer across all institutions."""

    provider_slug: str
    provider_id: Optional[str] = None
    external_id: Optional[str] = None
    fingerprint: Optional[str] = None
    title: str
    institution_name: str
    campus_or_unit: Optional[str] = None
    city: Optional[str] = None
    state: str = "SP"
    modality: str = "presencial"
    shift: str = "qualquer"
    price: Optional[float] = None
    is_free: bool = False
    has_scholarship: bool = False
    source_url: str
    status: str = "Indisponível"
    bolsa_disponivel: bool = False
    inscricao_disponivel: bool = False
    raw_data: Dict[str, Any] = Field(default_factory=dict)

    def compute_fingerprint(self) -> str:
        """Calculates stable deterministic SHA-256 hash for offer deduplication."""
        city_str = (self.city or "").lower().strip()
        payload = f"{self.provider_slug}:{self.title.lower().strip()}:{city_str}:{self.modality}:{self.shift}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.fingerprint = digest
        return digest

    def model_post_init(self, __context: Any) -> None:
        if not self.fingerprint:
            self.compute_fingerprint()


class SearchStatus(str, Enum):
    """Categorized status for a course offer search attempt."""

    COURSE_NOT_FOUND = "COURSE_NOT_FOUND"
    UNSUPPORTED_COURSE_TYPE = "UNSUPPORTED_COURSE_TYPE"
    NO_CLASSES_FOUND = "NO_CLASSES_FOUND"
    CLASSES_FOUND_NO_AVAILABILITY = "CLASSES_FOUND_NO_AVAILABILITY"
    AVAILABLE_OFFERS_FOUND = "AVAILABLE_OFFERS_FOUND"
    ERROR = "ERROR"


class ProviderSearchResult(BaseModel):
    """Structured diagnostic and operational search outcome from a provider."""

    provider_slug: str
    search_query: str
    status: SearchStatus
    course_name: Optional[str] = None
    course_url: Optional[str] = None
    article_id: Optional[str] = None
    codigo_ft: Optional[str] = None
    category: Optional[str] = None
    units_found: List[str] = Field(default_factory=list)
    classes_count: int = 0
    available_classes_count: int = 0
    raw_status_list: List[str] = Field(default_factory=list)
    offers: List[NormalizedOffer] = Field(default_factory=list)
    message: str = ""


class EducationProvider(ABC):
    """Abstract interface for education providers (Senac, Senai, Etec, Fatec).

    Ensures the core monitoring engine is completely decoupled from institution specifics.
    """

    enabled: bool = True

    @property
    def slug(self) -> str:
        """Returns unique slug of the provider (e.g. 'senac_sp')."""
        if hasattr(self, "institution_slug"):
            return self.institution_slug.replace("-", "_")
        return "senac_sp"

    @property
    def name(self) -> str:
        """Returns human readable name of the provider (e.g. 'Senac São Paulo')."""
        if hasattr(self, "institution_name"):
            return self.institution_name
        return "Senac São Paulo"

    @property
    def institution_slug(self) -> str:
        """Backward-compatible alias for slug."""
        return self.slug.replace("_", "-")

    @property
    def institution_name(self) -> str:
        """Backward-compatible alias for name."""
        return self.name

    def healthcheck(self) -> bool:
        """Returns True if provider backend/scraper is operational."""
        return True

    async def search_offers(self, query: str = "", **kwargs: Any) -> List[NormalizedOffer]:
        """Searches or lists normalized offers by query."""
        return []

    async def search_offers_structured(self, query: str = "", **kwargs: Any) -> ProviderSearchResult:
        """Executes search returning structured diagnostic result alongside normalized offers."""
        offers = await self.search_offers(query, **kwargs)
        if not offers:
            return ProviderSearchResult(
                provider_slug=self.slug,
                search_query=query,
                status=SearchStatus.COURSE_NOT_FOUND,
                message="Nenhuma oferta encontrada.",
            )
        available_count = len([o for o in offers if o.inscricao_disponivel or o.bolsa_disponivel])
        status = SearchStatus.AVAILABLE_OFFERS_FOUND if available_count > 0 else SearchStatus.CLASSES_FOUND_NO_AVAILABILITY
        return ProviderSearchResult(
            provider_slug=self.slug,
            search_query=query,
            status=status,
            classes_count=len(offers),
            available_classes_count=available_count,
            raw_status_list=[o.status for o in offers],
            offers=offers,
            message=f"{len(offers)} turma(s) encontrada(s).",
        )

    @abstractmethod
    async def get_offer_state(self, url_or_id: str) -> Union[OfferState, NormalizedOffer]:
        """Fetches and normalizes the current availability state of an offer."""
        pass

    async def get_locations(self) -> List[LocationData]:
        """Returns available campuses/units for this institution."""
        return []

    async def search_courses(self, query: str) -> List[CourseData]:
        """Searches course catalog by keyword."""
        return []

    async def discover_offers(
        self,
        course_name: str,
        unit_name: str,
        shift: Optional[str] = None,
    ) -> List[DiscoveredOffer]:
        """Discovers current and future offers matching course, unit, and shift."""
        return []
