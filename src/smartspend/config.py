"""Application settings and local data-directory helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DATA_DIR_ENV = "SMARTSPEND_DATA_DIR"
DATABASE_FILENAME = "smartspend.sqlite3"


@dataclass(frozen=True, slots=True)
class Settings:
    """Resolved paths used by the local application."""

    data_dir: Path
    database_path: Path


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Load settings, allowing the data directory to be overridden by environment."""
    environment = os.environ if environ is None else environ
    configured_data_dir = environment.get(DATA_DIR_ENV)
    data_dir = (
        Path(configured_data_dir).expanduser() if configured_data_dir else Path.cwd() / "data"
    ).resolve()

    return Settings(
        data_dir=data_dir,
        database_path=data_dir / DATABASE_FILENAME,
    )


def ensure_data_directory(settings: Settings | None = None) -> Path:
    """Create and return the configured data directory."""
    resolved_settings = load_settings() if settings is None else settings
    resolved_settings.data_dir.mkdir(parents=True, exist_ok=True)
    return resolved_settings.data_dir
