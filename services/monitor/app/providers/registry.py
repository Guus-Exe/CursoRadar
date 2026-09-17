"""Provider Registry for managing and discovering education providers."""

from typing import Dict, List, Optional
from app.providers.base import EducationProvider
from app.providers.senac import SenacSPProvider
from app.utils.logger import logger


class ProviderRegistry:
    """Registry to manage and discover multiple EducationProvider implementations."""

    def __init__(self) -> None:
        self._providers: Dict[str, EducationProvider] = {}

    def register(self, provider: EducationProvider) -> None:
        """Registers an EducationProvider by its slug."""
        self._providers[provider.slug] = provider
        logger.info(f"Provider '{provider.slug}' ({provider.name}) registrado com sucesso.")

    def get(self, slug: str) -> Optional[EducationProvider]:
        """Safely retrieves a provider by slug. Returns None if not found without unhandled exceptions."""
        if not slug:
            return None
        return self._providers.get(slug)

    def list_providers(self) -> List[EducationProvider]:
        """Lists all registered providers."""
        return list(self._providers.values())

    def get_active_providers(self) -> Dict[str, EducationProvider]:
        """Returns only enabled and healthy providers keyed by slug."""
        active: Dict[str, EducationProvider] = {}
        for slug, provider in self._providers.items():
            if getattr(provider, "enabled", True):
                try:
                    if provider.healthcheck():
                        active[slug] = provider
                except Exception as e:
                    logger.warning(f"Healthcheck falhou para provider '{slug}': {e}")
        return active


# Global/default registry pre-populated with Senac SP
default_registry = ProviderRegistry()
default_registry.register(SenacSPProvider())


def get_provider_registry() -> ProviderRegistry:
    """Returns the default provider registry instance."""
    return default_registry
