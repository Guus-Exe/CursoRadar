"""Abstract base EducationProvider interface for educational institutions."""

from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel
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


class EducationProvider(ABC):
    """Abstract interface for education providers (Senac, Senai, Etec, Fatec).
    
    Ensures the core monitoring engine is completely decoupled from institution specifics.
    """

    @property
    @abstractmethod
    def institution_slug(self) -> str:
        """Returns unique slug of the institution (e.g. 'senac-sp')."""
        pass

    @property
    @abstractmethod
    def institution_name(self) -> str:
        """Returns human readable name of the institution."""
        pass

    @abstractmethod
    async def get_locations(self) -> List[LocationData]:
        """Returns available campuses/units for this institution."""
        pass

    @abstractmethod
    async def search_courses(self, query: str) -> List[CourseData]:
        """Searches course catalog by keyword."""
        pass

    @abstractmethod
    async def discover_offers(
        self,
        course_name: str,
        unit_name: str,
        shift: Optional[str] = None,
    ) -> List[DiscoveredOffer]:
        """Discovers current and future offers matching course, unit, and shift."""
        pass

    @abstractmethod
    async def get_offer_state(self, url_or_id: str) -> OfferState:
        """Fetches and normalizes the current availability state of an offer."""
        pass
