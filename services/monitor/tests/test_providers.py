"""Tests for EducationProvider abstraction and SenacSPProvider."""

import pytest
from app.providers.base import EducationProvider, LocationData, CourseData
from app.providers.senac import SenacSPProvider


@pytest.mark.asyncio
async def test_senac_provider_locations():
    """Validates that SenacSPProvider implements EducationProvider and returns campuses."""
    provider = SenacSPProvider()
    assert isinstance(provider, EducationProvider)
    assert provider.institution_slug == "senac-sp"
    assert provider.institution_name == "Senac São Paulo"

    locations = await provider.get_locations()
    assert len(locations) >= 5
    assert any(loc.name == "Senac Lapa Faustolo" for loc in locations)
    assert any(loc.city == "São Paulo" for loc in locations)


@pytest.mark.asyncio
async def test_senac_provider_search_courses():
    """Validates course search via provider."""
    provider = SenacSPProvider()

    all_courses = await provider.search_courses("")
    assert len(all_courses) >= 5

    filtered = await provider.search_courses("vestuário")
    assert len(filtered) == 1
    assert filtered[0].name == "Técnico em Modelagem do Vestuário"
    assert filtered[0].external_id == "52620802"

    filtered_adm = await provider.search_courses("administração")
    assert len(filtered_adm) == 1
    assert "Administração" in filtered_adm[0].name
