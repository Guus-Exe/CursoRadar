"""Shared test fixtures."""

import os
from pathlib import Path
import pytest
from app.database import Database

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def offer_sem_vaga_xml(fixtures_dir: Path) -> str:
    with open(fixtures_dir / "offer_sem_vaga.xml", "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def offer_com_vaga_xml(fixtures_dir: Path) -> str:
    with open(fixtures_dir / "offer_com_vaga.xml", "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def offer_bolsa_aberta_xml(fixtures_dir: Path) -> str:
    with open(fixtures_dir / "offer_bolsa_aberta.xml", "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def sample_page_html(fixtures_dir: Path) -> str:
    with open(fixtures_dir / "sample_page.html", "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def temp_db(tmp_path: Path) -> Database:
    db_path = tmp_path / "test_monitor.db"
    return Database(f"sqlite:///{db_path}")
