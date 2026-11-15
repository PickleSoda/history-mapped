"""Fetch a batch of QIDs as the raw dicts EntityMapper.map() expects.

Four small WDQS queries per batch (core fields, dated statements with
precision, aliases, relationship properties) instead of one wide query, so
multi-valued properties never multiply into a cartesian product, plus one
MediaWiki call per 20 Wikipedia titles for the lead paragraph.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Callable

from pipeline.bulk.wdqs import Client, QueryTimeout, qid_of, value
from pipeline.wikidata.mapper.type_configs import WIKIDATA_TYPE_CONFIGS

logger = logging.getLogger(__name__)

# Date properties -> the raw key EntityMapper reads. Later entries only fill
# a key the earlier ones left empty.
DATE_PROPS: list[tuple[str, str]] = [
    ("P571", "inception"),
    ("P576", "dissolution"),
    ("P580", "start_time"),
    ("P582", "end_time"),
    ("P585", "point_in_time"),
    ("P569", "birth_date"),
    ("P570", "death_date"),
    ("P577", "inception"),  # publication date
    ("P1191", "inception"),  # first performance
    ("P575", "inception"),  # time of discovery or invention
    ("P1319", "inception"),  # earliest date
    ("P1326", "dissolution"),  # latest date
    ("P1317", "point_in_time"),  # floruit
]
START_KEYS = ("inception", "start_time", "birth_date", "point_in_time")

# Linked-place properties every type fetches (as in `pipeline scrape`), less
# P3896 geoshape, which would mean one Commons download per row.
BASE_PROPS = ["P17", "P131", "P276", "P36", "P1376", "P361", "P527", "P155", "P156"]

WKT_POINT = re.compile(r"^Point\(\s*(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s*\)$")
EXTRACT_CHARS = 1500


def rdf_year(dt: str | None) -> int | None:
    """Historical year of a WDQS xsd:dateTime ('-0489-01-01T…' is 490 BCE).

    WDQS writes XSD 1.1 (astronomical) years, where 0000 is 1 BCE; the atlas
    stores historical years, with no year 0.
    """
    if not dt:
        return None
    m = re.match(r"^([+-]?)(\d+)-", dt)
    if not m:
        return None
    year = int(m.group(2)) * (-1 if m.group(1) == "-" else 1)
    return year - 1 if year <= 0 else year


def point(wkt: str | None) -> dict[str, float] | None:
    """{lon, lat} of an Earth WKT point; None for other globes or junk."""
    if not wkt:
        return None
    m = WKT_POINT.match(wkt.strip())
    if not m:  # '<http://www.wikidata.org/entity/Q405> Point(…)' is the Moon
        return None
    lon, lat = float(m.group(1)), float(m.group(2))
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    return {"lon": lon, "lat": lat}


def _values(qids: list[str]) -> str:
    return " ".join(f"wd:{q}" for q in qids)


def fetch_core(client: Client, qids: list[str]) -> dict[str, dict[str, Any]]:
    rows = client.sparql(f"""
SELECT ?item ?label ?desc ?wp ?sl
       (GROUP_CONCAT(DISTINCT STRAFTER(STR(?c), "entity/"); separator="|") AS ?p31)
       (SAMPLE(?coord) AS ?co)
WHERE {{
  VALUES ?item {{ {_values(qids)} }}
  OPTIONAL {{ ?item rdfs:label ?label . FILTER(LANG(?label) = "en") }}
  OPTIONAL {{ ?item schema:description ?desc . FILTER(LANG(?desc) = "en") }}
  OPTIONAL {{ ?wpa schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?wp . }}
  OPTIONAL {{ ?item wikibase:sitelinks ?sl . }}
  OPTIONAL {{ ?item wdt:P31 ?c . }}
  OPTIONAL {{ ?item wdt:P625 ?coord . }}
}} GROUP BY ?item ?label ?desc ?wp ?sl""")
    out: dict[str, dict[str, Any]] = {}
    for b in rows:
        qid = qid_of(value(b, "item"))
        if not qid or qid in out:
            continue
        p31 = value(b, "p31") or ""
        out[qid] = {
            "qid": qid,
            "label": (value(b, "label") or "").strip(),
            "description": value(b, "desc") or "",
            "aliases": [],
            "coords": point(value(b, "co")),
            "wikipedia_title": value(b, "wp"),
            "sitelinks": int(value(b, "sl") or 0),
            "p31": [q for q in p31.split("|") if q],
            "properties": {},
        }
    return out


def fetch_dates(client: Client, qids: list[str], items: dict[str, dict[str, Any]]) -> None:
    pairs = " ".join(f'(p:{p} psv:{p} "{p}")' for p, _ in DATE_PROPS)
    rows = client.sparql(f"""
SELECT ?item ?pid ?t ?prec ?rank WHERE {{
  VALUES ?item {{ {_values(qids)} }}
  VALUES (?p ?psv ?pid) {{ {pairs} }}
  ?item ?p ?st . ?st ?psv ?tv . ?st wikibase:rank ?rank .
  ?tv wikibase:timeValue ?t ; wikibase:timePrecision ?prec .
  FILTER(?rank != wikibase:DeprecatedRank)
}}""")
    best: dict[tuple[str, str], tuple] = {}
    for b in rows:
        qid, pid = qid_of(value(b, "item")), value(b, "pid")
        year = rdf_year(value(b, "t"))
        if not qid or not pid or year is None or qid not in items:
            continue
        prec = int(value(b, "prec") or 0)
        preferred = (value(b, "rank") or "").endswith("PreferredRank")
        # Preferred rank first, then the most precise, then the earliest.
        key = (0 if preferred else 1, -prec, year)
        if (qid, pid) not in best or key < best[(qid, pid)][0]:
            best[(qid, pid)] = (key, year, prec)
    fill_dates(items, {k: (year, prec) for k, (_, year, prec) in best.items()})


def fill_dates(items: dict[str, dict[str, Any]], best: dict[tuple[str, str], tuple[int, int]]) -> None:
    """Set each item's raw date keys from its best value per property.

    In DATE_PROPS order, so inception (P571) wins over publication date
    (P577), except that a century-or-coarser value gives way to a later
    property's year-precision value: a novel whose P571 is "19th century"
    takes its P577 year.
    """
    for qid, item in items.items():
        for pid, raw_key in DATE_PROPS:
            found = best.get((qid, pid))
            if not found:
                continue
            year, prec = found
            precs = item.setdefault("_date_prec", {})
            if item.get(raw_key) is None or (precs.get(raw_key, 9) <= 7 and prec >= 9):
                item[raw_key] = str(year)
                precs[raw_key] = prec


def fetch_aliases(client: Client, qids: list[str], items: dict[str, dict[str, Any]]) -> None:
    rows = client.sparql(f"""
SELECT ?item ?alias WHERE {{
  VALUES ?item {{ {_values(qids)} }}
  ?item skos:altLabel ?alias . FILTER(LANG(?alias) = "en")
}}""")
    for b in rows:
        qid = qid_of(value(b, "item"))
        alias = (value(b, "alias") or "").strip()
        if qid in items and alias and alias not in items[qid]["aliases"]:
            items[qid]["aliases"].append(alias)


def fetch_properties(
    client: Client, qids: list[str], items: dict[str, dict[str, Any]], entity_type: str
) -> None:
    config = WIKIDATA_TYPE_CONFIGS.get(entity_type, {})
    props = [p for p in dict.fromkeys(config.get("property_queries", []) + BASE_PROPS) if p != "P3896"]
    if not props:
        return
    rows = client.sparql(f"""
SELECT ?item ?prop ?value ?valueLabel WHERE {{
  VALUES ?item {{ {_values(qids)} }}
  VALUES ?prop {{ {" ".join(f"wdt:{p}" for p in props)} }}
  ?item ?prop ?value .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}""")
    for b in rows:
        qid = qid_of(value(b, "item"))
        if qid not in items:
            continue
        prop = (value(b, "prop") or "").rsplit("/", 1)[-1]
        uri = value(b, "value") or ""
        label = value(b, "valueLabel") or ""
        vqid = qid_of(uri)
        if vqid and label == vqid:
            label = ""  # no English label
        # No coordinates on linked places: a row is never placed at its
        # country's or region's point (location policy: own P625 or OHM).
        items[qid]["properties"].setdefault(prop, []).append({"qid": vqid, "label": label, "uri": uri})


def shares_word(title: str, target: str) -> bool:
    """Whether a redirect keeps a word of its title ("Ibn Taymiyya" -> "Ibn
    Taymiyyah"), unlike one into a group article ("Paul Betz" -> "Knight's
    Cross of the Iron Cross")."""
    words = lambda s: {w for w in re.findall(r"\w+", s.lower()) if len(w) >= 3}  # noqa: E731
    return title == target or bool(words(title) & words(target))


def fetch_extracts(client: Client, items: list[dict[str, Any]]) -> None:
    """The lead paragraph of each item's English Wikipedia article."""
    by_title: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if item.get("wikipedia_title"):
            by_title.setdefault(item["wikipedia_title"], []).append(item)
    titles = list(by_title)
    for i in range(0, len(titles), 20):
        batch = titles[i : i + 20]
        data = client.wikipedia({
            "action": "query",
            "prop": "extracts",
            "exintro": "1",
            "explaintext": "1",
            "exchars": str(EXTRACT_CHARS),
            "redirects": "1",
            "titles": "|".join(batch),
        })
        query = data.get("query", {})
        resolved: dict[str, str] = {t: t for t in batch}
        sectioned: set[str] = set()
        for hop in query.get("normalized", []) + query.get("redirects", []):
            for src, dst in list(resolved.items()):
                if dst == hop.get("from"):
                    resolved[src] = hop.get("to")
                    if hop.get("tofragment"):
                        sectioned.add(src)
        extract_by_title = {p.get("title"): p.get("extract") or "" for p in query.get("pages", [])}
        for title in batch:
            if title in sectioned or not shares_word(title, resolved[title]):
                continue  # a redirect into a group article: its lead is about something else
            text = (extract_by_title.get(resolved[title]) or "").strip()
            if not text:
                continue
            first = text.split("\n", 1)[0].strip()
            for item in by_title[title]:
                item["summary"] = first[:900]
                item["full_extract"] = text


RETRY_PAUSE = 30.0


def split_retry(call: Callable[[list[str]], None], qids: list[str], label: str) -> None:
    """Run call(qids), surviving WDQS timeouts: pause and retry once, then
    halve the batch. A single QID that still times out is skipped (logged),
    so one slow item never kills a whole slice's fetch."""
    for attempt in range(2):
        try:
            call(qids)
            return
        except QueryTimeout as exc:
            reason = exc
            if attempt == 0:
                time.sleep(RETRY_PAUSE)
    if len(qids) == 1:
        logger.warning("%s: %s timed out twice (%s); skipped", label, qids[0], reason)
        return
    mid = len(qids) // 2
    split_retry(call, qids[:mid], label)
    split_retry(call, qids[mid:], label)


def fetch_batch(client: Client, qids: list[str], entity_type: str, wikipedia: bool = True) -> list[dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    split_retry(lambda b: items.update(fetch_core(client, b)), qids, "core")
    if not items:
        return []
    present = list(items)
    split_retry(lambda b: fetch_dates(client, b, items), present, "dates")
    split_retry(lambda b: fetch_aliases(client, b, items), present, "aliases")
    split_retry(lambda b: fetch_properties(client, b, items, entity_type), present, "properties")
    raws = [items[q] for q in qids if q in items]
    if wikipedia:
        fetch_extracts(client, raws)
    return raws


def start_precision(raw: dict[str, Any]) -> int | None:
    """Precision of the date that becomes the row's start (9 = year)."""
    precs = raw.get("_date_prec") or {}
    for key in START_KEYS:
        if raw.get(key) is not None and key in precs:
            return precs[key]
    return None
