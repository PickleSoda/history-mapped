"""Cached HTTP for the map-story authoring tools (research, places, queue).

Every response is cached on disk under output/map-stories/cache/ (the same
directory and key scheme as `geo._cached_get`, so the two share hits).
OpenStreetMap and OpenTopoData calls hold geo's `.ratelimit` lock, so all
processes together make at most one call a second; Wikimedia calls are made
one at a time without the lock.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Iterable

import requests

from pipeline.map_stories.geo import CACHE_DIR

USER_AGENT = "history-mapped/1.0 (https://github.com/PickleSoda/history-mapped)"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
SLOW_HOSTS = ("nominatim.openstreetmap.org", "api.opentopodata.org")


def cache_path(url: str, params: dict) -> Path:
    key = hashlib.sha1((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    return CACHE_DIR / f"{key}.json"


def _wait_for_slot() -> None:
    """One call a second across every process (Nominatim's usage policy)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_DIR / ".ratelimit", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        lock.seek(0)
        stamp = lock.read().strip()
        try:
            last = float(stamp) if stamp else 0.0
        except ValueError:
            last = 0.0
        wait = 1.1 - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        lock.seek(0)
        lock.truncate()
        lock.write(str(time.time()))
        lock.flush()
        fcntl.flock(lock, fcntl.LOCK_UN)


def get_json(url: str, params: dict, refresh: bool = False) -> Any:
    """GET `url` as JSON, from the disk cache when possible."""
    cached = cache_path(url, params)
    if cached.exists() and not refresh:
        return json.loads(cached.read_text())
    slow = any(h in url for h in SLOW_HOSTS)
    for attempt in range(3):
        if slow:
            _wait_for_slot()
        resp = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=45)
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < 2:
            time.sleep(min(10.0, float(resp.headers.get("Retry-After") or 2 * (attempt + 1))))
            continue
        resp.raise_for_status()
        break
    data = resp.json()
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(data, ensure_ascii=False))
    return data


# ── Wikidata ──────────────────────────────────────────────────────────────

DATE_PROPS = ("P585", "P580", "P582", "P569", "P570", "P571", "P576")


def _time(value: dict) -> str:
    """A Wikidata time value as '1815-06-18', '-216' or '1066-10'."""
    t, prec = value.get("time", ""), value.get("precision", 9)
    sign = "-" if t.startswith("-") else ""
    ymd = t.lstrip("+-").split("T")[0].split("-")
    year = ymd[0].lstrip("0") or "0"
    if prec >= 11:
        return f"{sign}{year}-{ymd[1]}-{ymd[2]}"
    if prec == 10:
        return f"{sign}{year}-{ymd[1]}"
    return f"{sign}{year}"


def _claims(entity: dict, prop: str) -> list[Any]:
    out = []
    for c in entity.get("claims", {}).get(prop, []):
        snak = c.get("mainsnak", {})
        if snak.get("snaktype") == "value":
            out.append(snak.get("datavalue", {}).get("value"))
    return out


def summarise(entity: dict) -> dict:
    """The few fields the tools use from a full wbgetentities entity."""
    coord = next(iter(_claims(entity, "P625")), None)
    amount = next(iter(_claims(entity, "P1120")), None)
    return {
        "id": entity.get("id"),
        "label": entity.get("labels", {}).get("en", {}).get("value"),
        "description": entity.get("descriptions", {}).get("en", {}).get("value"),
        "p31": [v.get("id") for v in _claims(entity, "P31") if isinstance(v, dict)],
        "p710": [v.get("id") for v in _claims(entity, "P710") if isinstance(v, dict)],
        "casualties": amount.get("amount", "").lstrip("+") if isinstance(amount, dict) else None,
        "coord": [round(coord["longitude"], 5), round(coord["latitude"], 5)] if isinstance(coord, dict) else None,
        "dates": {p: _time(v) for p in DATE_PROPS for v in _claims(entity, p)[:1] if isinstance(v, dict)},
        "sitelinks": len(entity.get("sitelinks", {})),
        "enwiki": entity.get("sitelinks", {}).get("enwiki", {}).get("title"),
        "missing": "missing" in entity,
    }


def _batched(ids: Iterable[str], kind: str, props: str, reduce, refresh: bool) -> dict[str, dict]:
    ids = list(dict.fromkeys(i for i in ids if i))
    out: dict[str, dict] = {}
    todo = []
    for qid in ids:
        f = CACHE_DIR / kind / f"{qid}.json"
        if f.exists() and not refresh:
            out[qid] = json.loads(f.read_text())
        else:
            todo.append(qid)
    def params(chunk: list[str]) -> dict:
        return {"action": "wbgetentities", "ids": "|".join(chunk), "props": props, "languages": "en", "format": "json"}

    def save(qid: str, row: dict) -> None:
        f = CACHE_DIR / kind / f"{qid}.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(row, ensure_ascii=False))
        out[qid] = row

    chunks = [todo[i : i + 50] for i in range(0, len(todo), 50)]
    while chunks:
        chunk = chunks.pop(0)
        data = get_json(WIKIDATA_API, params(chunk), refresh=True)
        # The raw batch is reduced into per-Q-id files below; drop the bulky original.
        cache_path(WIKIDATA_API, params(chunk)).unlink(missing_ok=True)
        if "error" in data:
            # One bad id fails the whole batch: retry the ids one by one.
            if len(chunk) > 1:
                chunks = [[q] for q in chunk] + chunks
            else:
                save(chunk[0], {"id": chunk[0], "missing": True})
            continue
        for qid, ent in (data.get("entities") or {}).items():
            save(qid, reduce(ent))
    return out


def wd_entities(qids: Iterable[str], refresh: bool = False) -> dict[str, dict]:
    """Summaries (label, description, P31, dates, coordinates, sitelink count)
    of many Q-ids, 50 per request, cached per Q-id."""
    return _batched(qids, "wd", "labels|descriptions|claims|sitelinks", summarise, refresh)


def wd_labels(qids: Iterable[str], refresh: bool = False) -> dict[str, str]:
    """English labels only (cheap; for P31 classes and participants)."""
    rows = _batched(qids, "wdl", "labels", lambda e: {"label": e.get("labels", {}).get("en", {}).get("value")}, refresh)
    return {q: (r.get("label") or q) for q, r in rows.items()}


def wd_search(name: str, limit: int = 7) -> list[str]:
    """Q-ids whose label or alias matches `name`."""
    data = get_json(WIKIDATA_API, {"action": "wbsearchentities", "search": name, "language": "en", "limit": limit, "type": "item", "format": "json"})
    return [h["id"] for h in data.get("search", [])]
