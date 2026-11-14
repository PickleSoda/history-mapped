"""pipeline.local_db.dsn: DATABASE_URL first, then pipeline/.env, local hosts only."""
from __future__ import annotations

import pytest

from pipeline import local_db


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "pipeline").mkdir()
    monkeypatch.setattr(local_db, "REPO", tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    return tmp_path


def test_reads_the_environment_first(repo, monkeypatch):
    (repo / "pipeline" / ".env").write_text("DATABASE_URL=postgresql://u:p@localhost:5999/from_file\n")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@127.0.0.1:5433/from_env")
    assert local_db.dsn() == "postgresql://u:p@127.0.0.1:5433/from_env"


def test_then_pipeline_env_then_the_local_default(repo):
    assert local_db.dsn() == local_db.LOCAL_DEFAULT
    (repo / "pipeline" / ".env").write_text("OTHER=1\nDATABASE_URL=postgresql://u:p@db:5432/hm\n")
    assert local_db.dsn() == "postgresql://u:p@db:5432/hm"


def test_refuses_a_remote_host(repo, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@203.0.113.7:5432/hm")
    with pytest.raises(SystemExit, match="non-local"):
        local_db.dsn()
