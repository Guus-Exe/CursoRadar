"""Abstract base scraper interface."""

from abc import ABC, abstractmethod
from typing import List, Optional
from app.models import DiscoveredOffer, OfferState


class BaseScraper(ABC):
    """Abstract interface for scrapers."""

    @abstractmethod
    async def get_offer_state(self, url_or_id: str) -> OfferState:
        """Fetches and parses current offer state."""
        pass

    @abstractmethod
    async def discover_new_offers(
        self, course_name: str, unit_name: str, shift: Optional[str] = None
    ) -> List[DiscoveredOffer]:
        """Searches for offers matching criteria."""
        pass
