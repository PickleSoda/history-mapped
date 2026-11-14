"""The database the standalone pipeline scripts read and write.

`DATABASE_URL` from the environment, else from `pipeline/.env`, else the local
dev database. Only a local host is accepted: these scripts are for the dev
database (a forwarded port or the compose `db` host), never a remote one.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOCAL_DEFAULT = "postgresql://history-mapped:secret@localhost:5432/history-mapped"
LOCAL_HOSTS = ("localhost", "127.0.0.1", "db")


def dsn() -> str:
    """The connection URL; exits rather than return a non-local host."""
    url = os.environ.get("DATABASE_URL")
    env = REPO / "pipeline" / ".env"
    if not url and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip()
    url = url or LOCAL_DEFAULT
    host = url.split("@")[-1].split("/")[0].split(":")[0]
    if host not in LOCAL_HOSTS:
        raise SystemExit(f"refusing to run against non-local database host {host!r}")
    return url
