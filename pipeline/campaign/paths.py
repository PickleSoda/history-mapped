"""Campaign file layout and run-id/slug resolution.

All paths hang off the repo root (override with CAMPAIGN_ROOT, used by tests).
Ingestion manifests live under AgentConfig.output_dir, resolved the same way the
`python -m pipeline agent` CLI resolves it (pipeline/.env, AGENT_OUTPUT_DIR).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_PREFIX = "campaign_"
FACT_LINE = re.compile(r"^\s*\d+[.)]")
FACT_NUM = re.compile(r"^\s*(\d+)[.)]")
SLUG_PARTS = re.compile(r"^(e\d{2})__(.+?)__(.+)$")


def root() -> Path:
    return Path(os.environ.get("CAMPAIGN_ROOT") or REPO_ROOT)


def slug_of(run: str) -> str:
    """Accept run_id, bare slug, transcript filename or candidates.json path."""
    s = run.strip().rstrip("/")
    if "/" in s or s.endswith(".json"):
        p = Path(s)
        s = p.parent.name if p.suffix == ".json" else p.name
    if s.endswith(".txt"):
        s = s[: -len(".txt")]
    if s.startswith(RUN_PREFIX):
        s = s[len(RUN_PREFIX):]
    if not s:
        raise ValueError(f"empty run name: {run!r}")
    return s


def run_id_of(run: str) -> str:
    return RUN_PREFIX + slug_of(run)


def parse_slug(slug: str) -> tuple[str, str, str]:
    """`e04__aegean__classical-greece` -> ("e04", "aegean", "classical-greece")."""
    m = SLUG_PARTS.match(slug)
    if not m:
        return "?", "?", slug
    return m.group(1), m.group(2), m.group(3)


def era_of(run: str) -> str | None:
    era = parse_slug(slug_of(run))[0]
    return None if era == "?" else era


def transcripts_dir() -> Path:
    return root() / "output" / "transcripts" / "campaign"


def extractions_dir() -> Path:
    return root() / "output" / "campaign" / "extractions"


def cache_dir() -> Path:
    return root() / "output" / "campaign" / "cache"


def transcript_path(run: str) -> Path:
    return transcripts_dir() / f"{slug_of(run)}.txt"


def transcript_rel(run: str) -> str:
    return f"output/transcripts/campaign/{slug_of(run)}.txt"


def handoff_dir(run: str) -> Path:
    return extractions_dir() / run_id_of(run)


def candidates_path(run: str) -> Path:
    return handoff_dir(run) / "candidates.json"


def review_path(run: str) -> Path:
    return handoff_dir(run) / "review.json"


def manifests_dir() -> Path:
    import pipeline.config  # noqa: F401  loads pipeline/.env like the agent CLI does
    from pipeline.agent.config import AgentConfig

    out = Path(AgentConfig().output_dir)
    return out if out.is_absolute() else root() / out


def manifest_path(run: str, base: Path | None = None) -> Path:
    return (base or manifests_dir()) / run_id_of(run) / "manifest.json"


def fact_lines(path: Path) -> dict[int, str] | None:
    """{fact number: the numbered line verbatim}; None if the transcript is missing.
    A repeated number keeps its first line (transcript-check reports the repeat)."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    out: dict[int, str] = {}
    for line in text.splitlines():
        m = FACT_NUM.match(line)
        if m:
            out.setdefault(int(m.group(1)), line.strip())
    return out


def count_facts(path: Path) -> int | None:
    try:
        with path.open(encoding="utf-8") as f:
            return sum(1 for line in f if FACT_LINE.match(line))
    except FileNotFoundError:
        return None
