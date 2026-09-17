"""Abstract base EducationProvider interface and normalized models for educational institutions."""

from abc import ABC, abstractmethod
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
