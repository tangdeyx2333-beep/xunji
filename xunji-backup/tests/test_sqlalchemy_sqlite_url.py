import importlib
from pathlib import Path

import pytest


def _reload_session_module(monkeypatch: pytest.MonkeyPatch, database_url: str):
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URL", database_url)
    from app.db import session as session_module

    return importlib.reload(session_module)


def test_normalize_sqlite_url_creates_parent_dir_for_absolute_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "db_dir" / "xunji1.db"
    module = _reload_session_module(monkeypatch, "sqlite:///:memory:")

    assert not db_file.exists()
    assert not db_file.parent.exists()

    normalized = module._normalize_database_url(f"sqlite:///{db_file.as_posix()}")
    assert db_file.parent.exists()
    assert normalized.startswith("sqlite:///")


def test_normalize_sqlite_url_resolves_relative_path_against_project_root(monkeypatch: pytest.MonkeyPatch):
    module = _reload_session_module(monkeypatch, "sqlite:///:memory:")

    normalized = module._normalize_database_url("sqlite:///./xunji1.db")
    db_path = Path(module.make_url(normalized).database)

    assert db_path.is_absolute()
    assert db_path == (module._PROJECT_ROOT / "xunji1.db").resolve()


def test_normalize_sqlite_url_keeps_memory_database(monkeypatch: pytest.MonkeyPatch):
    module = _reload_session_module(monkeypatch, "sqlite:///:memory:")

    normalized = module._normalize_database_url("sqlite:///:memory:")
    assert normalized == "sqlite:///:memory:"
