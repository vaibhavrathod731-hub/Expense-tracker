"""Shared fixtures for SmartSpend tests."""

import pytest

from smartspend.config import DATA_DIR_ENV, Settings, load_settings


@pytest.fixture
def settings(tmp_path, monkeypatch) -> Settings:
    """Provide isolated settings backed by a temporary data directory."""
    data_dir = tmp_path / "smartspend-data"
    monkeypatch.setenv(DATA_DIR_ENV, str(data_dir))
    return load_settings()
