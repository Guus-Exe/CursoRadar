"""Abstract base notification provider interface."""

from abc import ABC, abstractmethod
from typing import Optional
from app.models import DiscoveredOffer, StateDiff


class NotificationProvider(ABC):
    """Abstract interface for all notification channels (Telegram, WhatsApp, etc.)."""

    @abstractmethod
    async def send_offer_alert(self, diff: StateDiff, url: str) -> bool:
        """Sends an alert about an opportunity / change in an offer."""
        pass

    @abstractmethod
    async def send_new_offer_alert(self, offer: DiscoveredOffer) -> bool:
        """Sends an alert when a new course offer is discovered."""
        pass

    @abstractmethod
    async def send_health_alert(self, consecutive_failures: int, details: Optional[str] = None) -> bool:
        """Sends a warning when consecutive check failures exceed threshold."""
        pass

    @abstractmethod
    async def send_message(self, text: str) -> bool:
        """Sends generic text message."""
        pass
