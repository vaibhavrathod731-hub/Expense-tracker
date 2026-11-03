"""Shared fixtures for SmartSpend tests."""

import pytest

from smartspend.config import DATA_DIR_ENV, Settings, load_settings
from smartspend.db.connection import open_connection
from smartspend.db.schema import initialize_database


@pytest.fixture
def settings(tmp_path, monkeypatch) -> Settings:
    """Provide isolated settings backed by a temporary data directory."""
    data_dir = tmp_path / "smartspend-data"
    monkeypatch.setenv(DATA_DIR_ENV, str(data_dir))
    return load_settings()


@pytest.fixture
def database_path(tmp_path):
    """Create an initialized database isolated to this test."""
    path = tmp_path / "smartspend-test.sqlite3"
    initialize_database(path)
    return path


@pytest.fixture
def db_connection(database_path):
    """Open the test database with foreign-key enforcement enabled."""
    with open_connection(database_path) as connection:
        yield connection
