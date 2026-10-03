"""Plain-text Wikipedia extracts and search for transcript gathering.

Responses are cached on disk (output/campaign/cache/wiki/); live requests are
throttled to <= 1/s across processes via a lock file in the cache directory.
"""
from __future__ import annotations

import fcntl
import hashlib
import html
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.campaign.paths import cache_dir

API = "https://en.wikipedia.org/w/api.php"
MIN_INTERVAL = 1.0
SKIP_SECTIONS = {
    "see also", "references", "notes", "further reading", "external links",
    "bibliography", "sources", "citations", "footnotes", "works cited", "explanatory notes",
}
LEAD = "(lead)"
_HEADING = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$")
_SENTENCE_SPLIT = re.compile(
    r"(?<!\bc\.)(?<!\bca\.)(?<!\bSt\.)(?<!\bMt\.)(?<!\bDr\.)(?<!\bU\.S\.)(?<=[.!?])\s+(?=[A-Z\"“'(\[])"
)
DATED = re.compile(
    r"\b\d{1,5}\s*(?:BCE|BC|CE|AD)\b"
    r"|\b(?:AD|CE)\s*\d{1,4}\b"
    r"|\b\d{1,2}(?:st|nd|rd|th)[\s-]+(?:century|centuries|millennium)\b"
    r"|\b(?:c|ca)\.\s*\d"
    r"|\bcirca\s+\d"
    r"|(?<![\d,.])\b\d{3,4}s?\b(?![,.]\d)"
)


def _user_agent() -> str:
    from pipeline.config import settings

    return f"{settings.wikidata_user_agent} history-mapped-campaign/1.0"


def _cache_file(kind: str, key: str) -> Path:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    safe = re.sub(r"[^A-Za-z0-9]+", "_", key)[:60].strip("_")
    return cache_dir() / "wiki" / f"{kind}_{safe}_{digest}.json"


def _throttle() -> None:
    lock = cache_dir() / "wiki" / ".throttle"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        try:
            last = float(f.read().strip() or 0)
        except ValueError:
            last = 0.0
        wait = last + MIN_INTERVAL - time.time()
        if wait > 0:
            time.sleep(wait)
        f.seek(0)
        f.truncate()
        f.write(str(time.time()))


def _http_get(params: dict[str, Any]) -> dict:
    import requests

    _throttle()
    resp = requests.get(API, params={**params, "format": "json", "formatversion": "2"},
                        headers={"User-Agent": _user_agent()}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _cached(kind: str, key: str, params: dict[str, Any], refresh: bool = False) -> dict:
    path = _cache_file(kind, key)
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    data = _http_get(params)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


@dataclass
class Page:
    requested: str
    title: str | None
    text: str


def fetch_page(title: str, refresh: bool = False) -> Page:
    data = _cached("page", title, {
        "action": "query", "prop": "extracts", "explaintext": "1",
        "exsectionformat": "wiki", "redirects": "1", "titles": title,
    }, refresh=refresh)
    pages = (data.get("query") or {}).get("pages") or []
    page = pages[0] if pages else {}
    if page.get("missing") or page.get("invalid") or not page.get("extract"):
        return Page(title, None, "")
    return Page(title, page.get("title"), page["extract"])


def search(query: str, limit: int = 5, refresh: bool = False) -> list[tuple[str, str]]:
    data = _cached("search", f"{query}|{limit}", {
        "action": "query", "list": "search", "srsearch": query, "srlimit": str(limit),
        "srprop": "snippet",
    }, refresh=refresh)
    hits = (data.get("query") or {}).get("search") or []
    return [(h.get("title", ""), _clean_snippet(h.get("snippet", ""))) for h in hits]


def _clean_snippet(snippet: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", snippet))).strip()


def sections(text: str) -> list[tuple[str, int, list[str]]]:
    """Split an exsectionformat=wiki extract into (heading, level, paragraphs)."""
    out: list[tuple[str, int, list[str]]] = [(LEAD, 1, [])]
    for line in text.splitlines():
        m = _HEADING.match(line.strip())
        if m:
            out.append((m.group(2), len(m.group(1)), []))
        elif line.strip():
            out[-1][2].append(line.strip())
    return out


def _select(secs: list[tuple[str, int, list[str]]], wanted: list[str]) -> list[tuple[str, int, list[str]]]:
    """Drop reference sections; with `wanted`, keep matching sections plus their subsections."""
    keep, inside = [], None
    wanted_l = [w.casefold() for w in wanted]
    for heading, level, paras in secs:
        if inside is not None and level <= inside:
            inside = None
        if heading.casefold() in SKIP_SECTIONS:
            continue
        if wanted_l:
            hit = any(w == "lead" and heading == LEAD or w in heading.casefold() for w in wanted_l)
            if hit and inside is None:
                inside = level
            if inside is None:
                continue
        keep.append((heading, level, paras))
    return keep


def split_sentences(paragraph: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(paragraph) if s.strip()]


def render(page: Page, *, dated: bool = False, max_chars: int = 6000,
           wanted_sections: list[str] | None = None) -> str:
    secs = _select(sections(page.text), wanted_sections or [])
    chunks: list[str] = []
    for heading, _level, paras in secs:
        if dated:
            lines = [f"- {s}" for p in paras for s in split_sentences(p) if DATED.search(s)]
        else:
            lines = paras
        if not lines:
            continue
        chunks.append(f"## {heading}" if heading != LEAD else "## (lead)")
        chunks.extend(lines)
    body = "\n".join(chunks)
    if len(body) > max_chars:
        cut = body.rfind("\n", 0, max_chars)
        body = body[: cut if cut > max_chars // 2 else max_chars].rstrip() + "\n[truncated]"
    return body
