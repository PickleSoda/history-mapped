"""Cached, rate-limited Wikidata client for the identity audit.

* ``wbgetentities`` in batches of 50 ids, parsed down to what the audit needs
  (labels, aliases, description, P31, P279, dates, enwiki title) and cached on
  disk, so a re-run costs no requests for ids it has seen.
* ``wbsearchentities`` per name, cached.
* Subclass closure (P279*) of instance-of classes against a fixed set of root
  classes, via the query service in batches of 200 classes, cached.

Every request carries the project User-Agent (never an e-mail address), keeps
under ``max_rps`` requests per second, and backs off on 429/503.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Iterable

import requests

USER_AGENT = "history-mapped/1.0 (https://github.com/PickleSoda/history-mapped)"
API = "https://www.wikidata.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"
QID_RE = re.compile(r"^Q[1-9]\d*$")

# Date properties kept per record: birth/death, inception/dissolved,
# start/end time, point in time, publication date.
DATE_PROPS = ("P569", "P570", "P571", "P576", "P580", "P582", "P585", "P577")
# Item-valued properties kept per record (``links``): where a thing is, what it
# is part of, who took part, made, founded or ruled it, and family ties. The
# QID-less reconcile (``reconcile.py``) checks them against the QIDs of a
# row's related rows, both ways.
LINK_PROPS = (
    "P17", "P131", "P276", "P706", "P30",          # country, admin area, location, terrain, continent
    "P361", "P527", "P607", "P793", "P1344",       # part of, has part, conflict, significant event, participant in
    "P710", "P1001", "P2348",                      # participant, applies to jurisdiction, time period
    "P50", "P170", "P112", "P88", "P84", "P127",   # author, creator, founded by, commissioned by, architect, owner
    "P27", "P53", "P22", "P25", "P26", "P40", "P3373", "P19", "P20", "P140",  # people
    "P36", "P1376", "P150", "P155", "P156", "P1365", "P1366", "P749", "P138",
)


def _parse_time(value: dict[str, Any]) -> tuple[int, int] | None:
    """(year, precision) of a Wikidata time value; '-0481-00-00T..' -> (-481, 9)."""
    t = value.get("time")
    if not isinstance(t, str):
        return None
    m = re.match(r"^([+-])0*(\d+)-", t)
    if not m:
        return None
    year = int(m.group(2)) * (-1 if m.group(1) == "-" else 1)
    precision = value.get("precision")
    return year, precision if isinstance(precision, int) else 9


def _best_time(statements: Any) -> tuple[int, int] | None:
    """Preferred-rank value first, then normal; deprecated never."""
    if not isinstance(statements, list):
        return None
    usable = [s for s in statements if isinstance(s, dict) and s.get("rank") != "deprecated"]
    preferred = [s for s in usable if s.get("rank") == "preferred"]
    for st in preferred + usable:
        try:
            value = st["mainsnak"]["datavalue"]["value"]
        except (KeyError, TypeError):
            continue
        if isinstance(value, dict):
            parsed = _parse_time(value)
            if parsed:
                return parsed
    return None


def _item_ids(statements: Any) -> list[str]:
    out: list[str] = []
    for st in statements or []:
        if not isinstance(st, dict) or st.get("rank") == "deprecated":
            continue
        try:
            qid = st["mainsnak"]["datavalue"]["value"]["id"]
        except (KeyError, TypeError):
            continue
        if qid not in out:
            out.append(qid)
    return out


def parse_entity(ent: dict[str, Any]) -> dict[str, Any]:
    """Reduce a wbgetentities entity to the audit's record."""
    labels = ent.get("labels") or {}
    label = (labels.get("en") or labels.get("mul") or {}).get("value", "")
    aliases: list[str] = []
    for lang in ("en", "mul"):
        for a in (ent.get("aliases") or {}).get(lang, []) or []:
            v = a.get("value") if isinstance(a, dict) else None
            if v and v not in aliases:
                aliases.append(v)
    if labels.get("mul") and labels.get("en") and labels["mul"].get("value") not in aliases:
        aliases.append(labels["mul"]["value"])
    claims = ent.get("claims") or {}
    dates = {}
    for prop in DATE_PROPS:
        parsed = _best_time(claims.get(prop))
        if parsed:
            dates[prop] = list(parsed)
    enwiki = ((ent.get("sitelinks") or {}).get("enwiki") or {}).get("title")
    links = {p: ids for p in LINK_PROPS if (ids := _item_ids(claims.get(p)))}
    return {
        "status": "ok",
        "label": label,
        "aliases": aliases,
        "description": ((ent.get("descriptions") or {}).get("en") or {}).get("value", ""),
        "p31": _item_ids(claims.get("P31")),
        "p279": _item_ids(claims.get("P279")),
        "dates": dates,
        "enwiki": enwiki,
        "links": links,
        "coord": _coord(claims.get("P625")),
    }


def _coord(statements: Any) -> list[float] | None:
    """[lat, lon] of the first non-deprecated P625 (Earth) value."""
    for st in statements or []:
        if not isinstance(st, dict) or st.get("rank") == "deprecated":
            continue
        try:
            v = st["mainsnak"]["datavalue"]["value"]
            return [float(v["latitude"]), float(v["longitude"])]
        except (KeyError, TypeError, ValueError):
            continue
    return None


class WikidataClient:
    def __init__(self, cache_dir: str | os.PathLike, *, max_rps: float = 4.0, offline: bool = False,
                 session: requests.Session | None = None, workers: int = 4):
        import threading

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_rps = max_rps
        self.workers = workers
        self._lock = threading.Lock()
        self.offline = offline
        self._session = session
        self._local = threading.local()
        self._last = 0.0
        self.requests_made = 0
        self.entities: dict[str, dict[str, Any]] = self._load_jsonl("wd-entities.jsonl", "qid")
        self.searches: dict[str, list[dict[str, Any]]] = {
            k: v["results"] for k, v in self._load_jsonl("wd-search.jsonl", "q").items()}
        self.titles: dict[str, str | None] = {
            k: v["qid"] for k, v in self._load_jsonl("wd-titles.jsonl", "t").items()}
        closure_path = self.cache_dir / "wd-class-roots.json"
        self.closure: dict[str, Any] = (json.loads(closure_path.read_text())
                                        if closure_path.exists() else {"checked": {}, "reached": {}})

    # ── cache files ──────────────────────────────────────────────────────────
    def _load_jsonl(self, name: str, key: str) -> dict[str, Any]:
        path = self.cache_dir / name
        out: dict[str, Any] = {}
        if path.exists():
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        try:
                            rec = json.loads(line)
                        except json.JSONDecodeError:
                            continue  # a line cut short by an interrupted run
                        out[rec[key]] = rec
        return out

    def _append(self, name: str, records: Iterable[dict[str, Any]]) -> None:
        with (self.cache_dir / name).open("a", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _save_closure(self) -> None:
        (self.cache_dir / "wd-class-roots.json").write_text(json.dumps(self.closure))

    # ── HTTP ─────────────────────────────────────────────────────────────────
    def _sess(self) -> requests.Session:
        """One session per thread (requests.Session is not thread-safe)."""
        if self._session is not None:
            return self._session
        sess = getattr(self._local, "session", None)
        if sess is None:
            sess = self._local.session = requests.Session()
            sess.headers["User-Agent"] = USER_AGENT
        return sess

    def _get(self, url: str, params: dict[str, str], timeout: int = 60) -> requests.Response:
        if self.offline:
            raise RuntimeError("offline: Wikidata request needed but the client is offline")
        delay = 5.0
        for attempt in range(7):
            with self._lock:  # one shared limiter across worker threads
                wait = self._last + 1.0 / self.max_rps - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                self._last = time.monotonic()
            try:
                resp = self._sess().get(url, params=params, timeout=timeout)
            except requests.RequestException:
                if attempt == 6:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 120)
                continue
            self.requests_made += 1
            if resp.status_code in (429, 503, 502, 504):
                try:
                    pause = float(resp.headers.get("Retry-After", delay))
                except ValueError:
                    pause = delay
                time.sleep(min(max(pause, delay), 180))
                delay = min(delay * 2, 120)
                continue
            resp.raise_for_status()
            return resp
        raise RuntimeError(f"Wikidata kept throttling: {url}")

    # ── entities ─────────────────────────────────────────────────────────────
    def get_entities(self, qids: Iterable[str], *, progress: bool = False,
                     need_links: bool = False) -> dict[str, dict[str, Any]]:
        """Records for ``qids`` (cached). A redirect record carries
        ``status='redirect'`` and ``redirect_to``; a deleted id ``status='missing'``.
        ``need_links`` refetches cached records written before ``links`` and
        ``coord`` were kept (the newer line wins when the cache is read back)."""
        wanted = sorted({q for q in qids if q and QID_RE.match(q)}, key=lambda q: int(q[1:]))
        todo = [q for q in wanted if q not in self.entities
                or (need_links and self.entities[q].get("status") == "ok" and "links" not in self.entities[q])]
        batches = [todo[i:i + 50] for i in range(0, len(todo), 50)]
        done = 0
        if self.workers > 1 and len(batches) > 1:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            with ThreadPoolExecutor(self.workers) as pool:
                futures = [pool.submit(self._fetch_batch, b) for b in batches]
                for fut in as_completed(futures):
                    done = self._store(fut.result(), done, len(todo), progress)
        else:
            for b in batches:
                done = self._store(self._fetch_batch(b), done, len(todo), progress)
        return {q: self.entities[q] for q in wanted if q in self.entities}

    def _fetch_batch(self, batch: list[str]) -> dict[str, dict[str, Any]]:
        data = self._get(API, {
            "action": "wbgetentities", "ids": "|".join(batch), "format": "json",
            "props": "info|labels|descriptions|aliases|claims|sitelinks",
            "languages": "en|mul", "sitefilter": "enwiki",
        }).json()
        got: dict[str, dict[str, Any]] = {}
        for key, ent in (data.get("entities") or {}).items():
            if "missing" in ent:
                got[ent.get("id", key)] = {"status": "missing"}
                continue
            real = ent.get("id", key)
            got[real] = parse_entity(ent)
            redirect = ent.get("redirects") or {}
            src = redirect.get("from") or (key if key != real else None)
            if src:
                got[src] = {"status": "redirect", "redirect_to": redirect.get("to", real)}
        for q in batch:
            got.setdefault(q, {"status": "missing"})
        return got

    def _store(self, got: dict[str, dict[str, Any]], done: int, total: int, progress: bool) -> int:
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        new = [{"qid": q, "fetched": stamp, **r} for q, r in got.items()
               if q not in self.entities or ("links" in r and "links" not in self.entities[q])]
        for rec in new:
            self.entities[rec["qid"]] = rec
        self._append("wd-entities.jsonl", new)
        before, done = done, done + len(got)
        if progress and before // 1000 != done // 1000:
            print(f"  wbgetentities ~{done}/{total}", flush=True)
        return done

    def resolved(self, qid: str) -> tuple[str, dict[str, Any] | None]:
        """(final qid, record) following redirects already in the cache."""
        seen = set()
        rec = self.entities.get(qid)
        while rec and rec.get("status") == "redirect" and qid not in seen:
            seen.add(qid)
            qid = rec["redirect_to"]
            rec = self.entities.get(qid)
        return qid, rec

    # ── enwiki titles ────────────────────────────────────────────────────────
    def by_titles(self, titles: Iterable[str], *, progress: bool = False) -> dict[str, str | None]:
        """{title: QID of the item whose enwiki article has exactly that title, or None}.

        ``wbgetentities`` with ``sites=enwiki``, 50 titles per call, cached in
        ``wd-titles.jsonl``. Wikipedia redirects are not followed, so a hit is
        an exact article title. The items come back whole and go into the
        entity cache too."""
        wanted = sorted({t for t in titles if t and len(t) < 250 and not set(t) & set("|#<>[]{}_")})
        todo = [t for t in wanted if t not in self.titles]
        for i in range(0, len(todo), 50):
            batch = todo[i:i + 50]
            data = self._get(API, {
                "action": "wbgetentities", "sites": "enwiki", "titles": "|".join(batch), "format": "json",
                "props": "info|labels|descriptions|aliases|claims|sitelinks",
                "languages": "en|mul", "sitefilter": "enwiki",
            }).json()
            found: dict[str, str] = {}
            got: dict[str, dict[str, Any]] = {}
            for key, ent in (data.get("entities") or {}).items():
                if "missing" in ent or not QID_RE.match(ent.get("id", "")):
                    continue
                rec = parse_entity(ent)
                got[ent["id"]] = rec
                if rec.get("enwiki"):
                    found[rec["enwiki"]] = ent["id"]
            self._store(got, 0, 0, False)
            rows = []
            for t in batch:
                # MediaWiki upper-cases the first letter and treats _ as a space
                norm = (t[:1].upper() + t[1:]).replace("_", " ")
                self.titles[t] = found.get(norm) or found.get(t)
                rows.append({"t": t, "qid": self.titles[t]})
            self._append("wd-titles.jsonl", rows)
            if progress and (i // 50) % 20 == 0:
                print(f"  enwiki titles {i + len(batch)}/{len(todo)}", flush=True)
        return {t: self.titles.get(t) for t in wanted}

    # ── search ───────────────────────────────────────────────────────────────
    def search(self, name: str, limit: int = 10) -> list[dict[str, Any]]:
        key = f"{name}\u241f{limit}"
        if key not in self.searches:
            self._store_search(key, self._search_fetch(name, limit))
        return self.searches[key]

    def search_many(self, names: Iterable[str], limit: int = 10) -> None:
        """Run the uncached searches in parallel (same shared rate limit)."""
        todo = sorted({n for n in names if n and f"{n}\u241f{limit}" not in self.searches})
        if not todo:
            return
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max(1, self.workers)) as pool:
            for name, results in zip(todo, pool.map(lambda n: self._search_fetch(n, limit), todo)):
                self._store_search(f"{name}\u241f{limit}", results)

    def _search_fetch(self, name: str, limit: int) -> list[dict[str, Any]]:
        data = self._get(API, {"action": "wbsearchentities", "search": name, "language": "en",
                               "uselang": "en", "type": "item", "limit": str(limit), "format": "json"}).json()
        return [{"qid": it.get("id"), "label": it.get("label", ""),
                 "description": it.get("description", ""),
                 "aliases": it.get("aliases", []) or [],
                 "match_type": (it.get("match") or {}).get("type", ""),
                 "match_text": (it.get("match") or {}).get("text", "")}
                for it in data.get("search", []) if it.get("id")]

    def _store_search(self, key: str, results: list[dict[str, Any]]) -> None:
        self.searches[key] = results
        self._append("wd-search.jsonl", [{"q": key, "results": results}])

    # ── subclass closure ─────────────────────────────────────────────────────
    def class_roots(self, classes: Iterable[str], roots: Iterable[str], *,
                    progress: bool = False) -> dict[str, set[str]]:
        """For each class, the subset of ``roots`` it is (a subclass of)."""
        roots = sorted(set(roots))
        classes = sorted({c for c in classes if QID_RE.match(c)})
        checked, reached = self.closure["checked"], self.closure["reached"]
        # group classes by the roots they still need checking against
        pending: dict[tuple[str, ...], list[str]] = {}
        for c in classes:
            missing = tuple(r for r in roots if r not in set(checked.get(c, [])))
            if missing:
                pending.setdefault(missing, []).append(c)
        for missing, group in pending.items():
            size = 50 if len(missing) > 20 else 200  # a few new roots are cheap to check
            for i in range(0, len(group), size):
                batch = group[i:i + size]
                self._closure_batch(batch, list(missing))
                self._save_closure()
                if progress:
                    print(f"  class closure {i + len(batch)}/{len(group)} (roots {len(missing)})", flush=True)
        return {c: set(reached.get(c, [])) & set(roots) for c in classes}

    def _closure_batch(self, batch: list[str], roots: list[str]) -> None:
        """One SELECT DISTINCT over batch × roots. The query service times out
        mid-stream on heavy batches (a truncated, unparseable body): split the
        batch and retry; a single class that still fails is recorded as
        reaching no root, and listed in ``closure_failures``."""
        checked, reached = self.closure["checked"], self.closure["reached"]
        query = ("SELECT DISTINCT ?c ?root WHERE { VALUES ?c { " + " ".join(f"wd:{c}" for c in batch)
                 + " } VALUES ?root { " + " ".join(f"wd:{r}" for r in roots) + " } ?c wdt:P279* ?root }")
        try:
            bindings = self._get(SPARQL, {"query": query, "format": "json"}, timeout=120).json()["results"]["bindings"]
        except (ValueError, KeyError, requests.RequestException, RuntimeError):
            if len(batch) > 1:
                half = len(batch) // 2
                self._closure_batch(batch[:half], roots)
                self._closure_batch(batch[half:], roots)
                return
            self.closure.setdefault("failures", [])
            if batch[0] not in self.closure["failures"]:
                self.closure["failures"].append(batch[0])
            bindings = []
        for b in bindings:
            c = b["c"]["value"].rsplit("/", 1)[-1]
            r = b["root"]["value"].rsplit("/", 1)[-1]
            reached.setdefault(c, [])
            if r not in reached[c]:
                reached[c].append(r)
        for c in batch:
            checked[c] = sorted(set(checked.get(c, [])) | set(roots))
