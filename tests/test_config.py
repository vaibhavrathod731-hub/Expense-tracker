from pathlib import Path

from smartspend.config import (
    DATA_DIR_ENV,
    DATABASE_FILENAME,
    ensure_data_directory,
    load_settings,
)


def test_load_settings_uses_configured_data_directory(tmp_path):
    configured_path = tmp_path / "custom-data"

    settings = load_settings({DATA_DIR_ENV: str(configured_path)})

    assert settings.data_dir == configured_path.resolve()
    assert settings.database_path == configured_path.resolve() / DATABASE_FILENAME


def test_load_settings_defaults_to_data_directory_under_current_working_directory(
    tmp_path, monkeypatch
):
    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    monkeypatch.chdir(tmp_path)

    settings = load_settings()

    assert settings.data_dir == (tmp_path / "data").resolve()
    assert settings.database_path == settings.data_dir / DATABASE_FILENAME


def test_ensure_data_directory_creates_configured_directory(settings):
    assert not settings.data_dir.exists()

    created_directory = ensure_data_directory(settings)

    assert created_directory == settings.data_dir
    assert Path(created_directory).is_dir()


def test_ensure_data_directory_is_idempotent(settings):
    ensure_data_directory(settings)

    assert ensure_data_directory(settings) == settings.data_dir
