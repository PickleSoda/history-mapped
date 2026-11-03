#!/usr/bin/env python3
"""Alias cleanup (2026-11-01): delete junk rows from ``entity_aliases``.

Aliases drive search, the importer's reference resolver (an alias names an
entity when exactly one entity holds it, case-insensitively) and the map-story
PlaceFinder, so a junk alias causes wrong links. Classes (checked in the order
same_as_name, case_duplicate, manual_junk, generic_word, nominatim_wrong_link):

  same_as_name          the alias is the entity's own name (case-insensitive):
                        every consumer compares lower-cased, so it adds nothing.
  case_duplicate        another alias of the same entity differs from it only in
                        case; the earliest row is kept.
  nominatim_wrong_link  the alias is the name of the OHM feature a name-only
                        (Nominatim) link matched — the old linker stored that
                        name as an alias ('Fifth Street' on the Fifth French
                        Republic) — and that link is wrong: the OHM-ref audit
                        (output/audit/ohm-refs-20261101/verdicts.csv) judged it
                        WRONG; or, for a link it did not judge, the feature is a
                        street, waterway, building, shop … on an entity of
                        another kind, or the feature name only adds a word of
                        another kind to the entity's name ('Hydro Maya Dam').
                        A link the audit judged OK, or whose feature carries the
                        entity's own QID, vouches for the name: kept.
  manual_junk           hand-checked rows (MANUAL_JUNK): Nominatim names of links the
                        audit could not judge, and another row's name that is
                        plainly another person or thing ('Henry Havelock' on
                        Lord Chelmsford).
  generic_word          the alias is one bare class noun ('Empire', 'King',
                        'Senate'), optionally with 'the' — deleted even when
                        Wikidata lists it, since it can only mislink.

Listed in review.csv, never deleted automatically: another row's primary name under
another QID (mostly a place's name in another era, a short form or a duplicate row),
Nominatim names of links nobody could judge, and the hand-kept MANUAL_KEEP rows.
The `language` column is empty on every row, so there is no script/language check.

Never deleted: is_primary rows, identity-audit rows (source 'identity-audit' and
the pins in output/audit/identity-20261031/pins.csv), rows of the excluded
entities (RULES.md), and — for nominatim_wrong_link — any alias that is a
Wikidata label or alias, in any language, of the entity's own QID. A deletion
that would leave the alias on exactly one other entity (so the resolver starts
linking it there) is skipped and listed, unless that other holder's alias is
itself Wikidata-verified.

Dry run by default: writes planned.csv and review.csv (kept, listed for a
human). --apply pg_dumps entity_aliases, writes rollback.sql (guarded
re-inserts), then deletes each planned row guarded on the values read (alias
row unchanged, entity name/QID unchanged) in one transaction, and writes
applied.csv.

    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.alias_cleanup            # dry run
    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.alias_cleanup --apply    # write
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.agent.tools.disambiguation import _name_tokens, names_equal  # noqa: E402
from pipeline.audit.common import COMPOSE, REPO, connect  # noqa: E402
from pipeline.audit.wd import API, QID_RE, USER_AGENT  # noqa: E402

OUT = REPO / "output" / "audit" / "aliases-20261101"
OHM_VERDICTS = REPO / "output" / "audit" / "ohm-refs-20261101" / "verdicts.csv"
MERGE_VERDICTS = REPO / "output" / "audit" / "merge-review-20261101" / "verdicts.csv"
PINS = REPO / "output" / "audit" / "identity-20261031" / "pins.csv"
USER_DECISION_PREFIXES = ("a05afb75", "6255478f", "17d96812", "7baeedc3")
PROTECTED_SOURCES = {"identity-audit"}

# One bare class noun is not a name: 'Empire' on the Sur Empire, 'King' on the Crown.
GENERIC = {
    "kingdom", "empire", "battle", "war", "republic", "dynasty", "state", "city", "town", "union",
    "crown", "king", "queen", "emperor", "empress", "sultan", "caliph", "khan", "pharaoh", "pope",
    "senate", "congress", "parliament", "council", "assembly", "court", "government", "army", "navy",
    "academy", "library", "mausoleum", "museum", "university", "school", "church", "temple", "mosque",
    "palace", "castle", "fort", "fortress", "monastery", "abbey", "cathedral", "monument", "tomb",
    "crusade", "history", "histories", "calendar", "treaty", "peace", "revolution", "rebellion", "revolt",
    "uprising", "massacre", "siege", "campaign", "expedition", "conquest", "invasion", "crisis",
    "period", "era", "age", "culture", "house", "family", "company", "people", "tribe", "organization",
    "sultanate", "caliphate", "khanate", "duchy", "county", "province", "colony", "federation",
    "confederation", "league", "alliance", "river", "bridge", "canal", "wall", "road", "golden",
}

# Feature kinds that name a thing, never a polity, person, event or idea.
THING_KEYS = ("highway", "waterway", "railway", "building", "shop", "amenity", "tourism", "leisure",
              "office", "craft", "man_made", "aeroway", "public_transport")
THING_TYPES = {
    "river", "stream", "canal", "lake", "pond", "reservoir", "dam", "weir", "residential", "primary",
    "secondary", "tertiary", "unclassified", "motorway", "motorway_junction", "trunk", "service",
    "footway", "pedestrian", "track", "road", "living_street", "station", "stop", "halt", "platform",
    "house", "yes", "hotel", "restaurant", "cafe", "pub", "bar", "fast_food", "mall", "supermarket",
    "post_office", "school", "university", "college", "hospital", "theatre", "cinema", "museum",
    "industrial", "commercial", "retail", "park", "garden", "pitch", "stadium", "parking", "fuel",
    "bank", "office", "car", "apartments", "place_of_worship", "government", "townhall", "memorial",
    "monument", "fort", "castle", "ruins", "archaeological_site", "square", "bridge",
}
# Words that name a kind of thing; one added to the entity's name makes another thing.
KIND_WORDS = {
    "street", "st", "road", "rd", "avenue", "ave", "lane", "boulevard", "drive", "court", "row",
    "highway", "station", "railway", "river", "creek", "lake", "brook", "canal", "dam", "bridge",
    "building", "hall", "house", "store", "shop", "hotel", "restaurant", "pavilion", "school",
    "park", "square", "plaza", "tower", "mall", "center", "centre", "camp", "mill", "farm", "church",
    "chapel", "cemetery", "museum", "library", "pond", "apartments", "inc", "llc", "ltd", "corporation",
    "co", "works", "office", "operations", "diocese", "pass", "island", "lodge", "club", "market",
    "pier", "zone", "village", "tribal", "hill",
}
# Entity types for which a place/building/waterway feature can be the thing itself.
PLACE_TYPES = {"city", "infrastructure_monument", "natural_resource", "extraction_infra", "trade_route",
               "educational_institution", "archaeological_culture"}

# Hand-checked (entity_id, alias) -> why it is junk. Read against the row's summary and the
# names of both QIDs during the 2026-11-01 spot check.
MANUAL_JUNK = {
    # Nominatim names of unjudged/unsure links (no QID to vouch either way)
    ("ecb6d711-63cd-4caf-9763-e7b4d775b4ed", "Abenaki Tribal Village"): "a village feature in Maine, not the people",
    ("e8eebc18-dbe7-435b-b1ec-5194e6184567", "Chamorro Time Zone"): "a time zone, not the people",
    ("032fd4a6-2538-48dc-a433-58e2e68f41dc", "Chedi Pier"): "a pier in Thailand, not the Mahajanapada",
    ("1f85246c-37c0-4f96-83e4-af3b2e3cd7ef", "Duck Creek"): "a creek in Delaware, not the Creek people",
    ("c69f85c8-5696-4c7f-9f1f-1c83f667f25e", "Dutch occupation of São Tomé"): "one episode, not the Dutch power",
    ("25f710f5-eed8-4fb7-b6fb-923c8bf20cfc", "Empire Hill"): "a hill in Missouri, not the Han Empire",
    ("b55bfe6c-b8bd-4d26-8b47-e0efcc699fe5", "Brownish House"): "a house in Savoie, not the House of Savoy",
    ("5d9f8006-e7a7-4990-bc2a-3861fc7eb239", "Hannover"): "the German city, not the Kingdom of Han",
    ("fbba5c0d-5f8d-48e6-aeaf-96fc16136fae", "Hörde"): "a district of Dortmund, not the Kok Horde",
    ("6f2e47f9-0718-4c41-ba57-56362d616602", "British Military Administration of Libya"):
        "the 1943-51 occupation regime, not the state of Libya",
    ("ba74ca53-a736-45fb-858b-ada86dfedd9c", "Res Publica Romana (BCE218-BCE212)"):
        "an OHM time-slice label with its dates, never a name in text",
    ("29408395-9a50-4f6d-9024-0df3659c0775", "Koh Rong"): "a Cambodian island, not the Rong peoples",
    ("c5187196-e0bd-4986-ae40-6e732e778d80", "Spanish Philippines"): "a colony, not the Spanish power",
    ("c4d3b9f0-e69b-412c-9475-317083682c02", "W. S. Buffham & Son"): "a shop in Wisconsin, not the Tay Son state",
    ("2580e5c5-a03e-46fe-9580-f58263b285b7", "Oʻzbekiston"): "modern Uzbekistan, not the 16th-c. Uzbek khanate",
    # The OHM feature carries the row's QID, but that QID is wrong for the row (listed for the identity audit)
    ("228680de-efc8-48fa-b82a-2634cadc416d", "Livonia Township"): "a Michigan township on medieval Livonia "
        "(the row's QID Q853552 looks like Livonia, Michigan)",
    ("f84d3b76-b3d3-4ba7-be5c-4bf99dc9cf6d", "Provincia di Mantova"): "an Italian province on the Ili region "
        "(the row's QID Q16204 is the province, wrong for the row)",
    # Another row's name, and plainly another person or thing
    ("b0a08ed7-5c4b-44cc-b69a-279f9c70286d", "Henry Havelock"): "another British general (d. 1857), not Lord Chelmsford",
    ("3adeedc3-21b5-4a32-852c-60e58c4ec05b", "Pope Sixtus II"): "Stephen I's successor, another pope",
    ("025f04bc-5528-4b04-9e65-57036143d444", "Axum"): "the Ethiopian kingdom, not Nubian Alodia",
    ("940fe063-2bb6-4511-900a-a20d621f181c", "firearms"): "a broader class (another row), not a name of artillery",
    ("47dfd71d-5558-41c8-a69c-3bda5b9ff655", "Spanish Texas"): "the preceding Spanish province (another row)",
    ("c4fb1f0d-0117-4f7d-8029-71ded8d35f55", "Spanish Netherlands"): "the preceding Spanish regime (another row)",
    ("a00a8add-22e6-4d5c-ab6f-c656cf7c4d92", "France"): "the colonial power, not French Algeria",
    ("7778f0d8-93d5-48e8-926d-c47bdff77efc", "Bahadur Shah of Gujarat"):
        "the 16th-c. Gujarat sultan; the row is the last Mughal emperor (Bahadur Shah II)",
    ("1ea45552-a266-4b7d-ad85-d74c4464266c", "Periplus of the Erythraean Sea"):
        "another text (1st c.), not the Adulis inscription Cosmas copied",
    ("1ac4f426-a96b-4e06-83e6-16af94446817", "Tlemcen"): "another Algerian city; Tahert is modern Tiaret",
}
# Hand-checked (entity_id, alias) kept although its Nominatim link was judged WRONG: the
# name itself is a real name of the row's subject.
MANUAL_KEEP = {
    ("836908ec-bdfa-4395-bba1-9fc96a94d641", "Guernica"): "Spanish name of Gernika (row QID Q5552361 looks wrong)",
    ("ea6ec9e6-e610-41cd-8bed-76575237061e", "Ticino"): "the canton's usual name (row QID Q115917508 is a football team)",
    ("1530240d-c0d0-4e5a-a1b1-575834d47507", "Pan American World Airways"): "Pan Am's full name from 1950",
    ("e0a9852c-ee15-49d3-9830-bc4073c68961", "Monarquía Hispánica"): "Spanish name of the early modern Spanish monarchy",
    ("075f76d6-9a43-42d7-a866-fb4675bebc98", "Djawa Timur"): "old spelling of Jawa Timur (East Java)",
    ("316e3bd3-ca69-43f0-b188-f652476acf43", "Provincia Arabia Petraea"): "Latin name of the province",
    ("81d971e1-f2b4-4a75-a775-e19a37d1e1f6", "Duché de Vasconie"): "the duchy Gascony grew from",
    # The row's summary is the polity the alias names, though its QID is the region/people
    # (OHM tagged the feature with the polity's own QID, hence 'other_qid_tag').
    ("d0fb2e50-0497-404f-b4c5-dc68554c37f9", "Kingdom of Pontus"): "the row is the Anatolian kingdom",
    ("17f03897-b465-4968-83e3-95605bf90530", "Königreich Preußen"): "the row is the Zollverein-era kingdom",
    ("19a4322e-66ef-4758-b7bc-f60e7c390eba", "Purépecha Empire"): "the row is the Purépecha state",
    ("40ba7085-9fcf-43cc-94c5-cf421566d96e", "Heerlijkheid Utrecht"): "the province's name in 1528-1795",
    ("3c1157d4-54a2-4086-8421-cc11ba089113", "Herzogtum Schleswig-Holstein-Gottorp"): "German name of the duchy",
    ("342e1a6c-649c-4e76-9fbf-76241eb2bad8", "Landschap Drenthe"): "Drenthe's historical name",
    ("21c23131-b3f0-495b-b7d9-bc8b1cf7420e", "Colony of Natal"): "the 1843 annexation made the Colony of Natal",
    ("2fcc7494-1e8f-4e88-a01a-34910c079021", "Reichsgau Sudetenland"): "the 1938 annexed territory's name",
    ("665ac497-cfb5-44e2-97c0-1f60efd48306", "Mgft. Brandenburg"): "abbreviated Markgrafschaft Brandenburg",
    ("a29ad302-a48a-4dd3-abfe-638d45a6954d", "Biskupie Księstwo Warmińskie"): "Polish name of the post-1466 polity",
    ("cd704223-1036-4c0b-a7a2-e7683ef2139d", "Regnum Langobardorum"): "the row covers the Lombards' kingdom",
    ("72ba23bc-3510-450e-8b50-1fe4e43e3975", "Itza Kingdom"): "the Itza's kingdom",
    ("c9d445a7-14dd-4891-953e-7bf8dd562375", "Matabeleland Protectorate"): "Matabeleland's colonial-era name",
    ("6b7921a3-81bd-4474-a3fc-c6c225d19a4c", "Obock et Protectorats de la Côte des Somalis et des pays Dankils"):
        "the colony's 1884-96 name",
    ("0e7ecdd5-e513-4ac1-94da-0eb1e2dfe31b", "DF Yugoslavia"): "Yugoslavia's 1943-45 name",
    ("d4f1cdf4-4ff2-40a5-9484-001d596d48da", "英屬香港 British Hong Kong"): "the row is the British colony",
    ("220e9c84-b81f-434c-92a8-2e5893ac73f0", "Mediterranean Sea"): "the row is the sea and its shores",
    ("57fb3efd-627f-4f59-9dc4-7e73b6a16201", "Rattanakosin Kingdom Mandala"): "OHM's label for the Thai kingdom",
    ("0387fe47-3061-4a79-84ca-5f1937cfc50f", "Ansbach"): "the principality's usual short name",
    ("4df69790-2a69-4680-89ae-361475f22653", "Aegean Sea"): "the row is the sea region",
}

PLANNED_FIELDS = ["reason", "alias_id", "entity_id", "entity_name", "entity_type", "qid", "alias",
                  "source", "created_at", "evidence"]


# ── names ────────────────────────────────────────────────────────────────────
def same_name(a: str, b: str) -> bool:
    """names_equal, or (for scripts it folds to nothing) the same casefolded text."""
    return names_equal(a, b) or a.strip().casefold() == b.strip().casefold()


def name_key(name: str) -> str:
    toks = _name_tokens(name)
    return " ".join(toks) if toks else name.strip().casefold()


# ── Wikidata: every label and alias, all languages ───────────────────────────
class WDNames:
    """{qid: record} with the names (labels + aliases, all languages) of each QID,
    cached in OUT/cache/wd-names.jsonl; wbgetentities 50 ids per call, ≤1 req/s,
    maxlag=5, backing off on 429/503/maxlag."""

    def __init__(self, cache_dir: Path, offline: bool = False):
        import requests

        self.path = cache_dir / "wd-names.jsonl"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self.recs: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self.recs[r["qid"]] = r
        self.sess = requests.Session()
        self.sess.headers["User-Agent"] = USER_AGENT
        self.requests = 0

    def fetch(self, qids: Iterable[str]) -> int:
        """Fetch the uncached QIDs; returns how many are still missing (Wikidata kept
        refusing: the caller treats those rows as unverifiable and deletes nothing on them)."""
        todo = sorted({q for q in qids if q and QID_RE.match(q) and q not in self.recs}, key=lambda q: int(q[1:]))
        if not todo or self.offline:
            return len(todo)
        for i in range(0, len(todo), 50):
            batch = todo[i:i + 50]
            try:
                data = self._get({"action": "wbgetentities", "ids": "|".join(batch), "props": "labels|aliases",
                                  "format": "json", "maxlag": "5"})
            except RuntimeError as exc:
                print(f"  wd names: giving up ({exc}); {len(todo) - i} QIDs left unfetched", flush=True)
                return len(todo) - i
            got: dict[str, dict[str, Any]] = {}
            for key, ent in (data.get("entities") or {}).items():
                if "missing" in ent:
                    got[ent.get("id", key)] = {"status": "missing"}
                    continue
                real = ent.get("id", key)
                names: list[str] = []
                for v in (ent.get("labels") or {}).values():
                    if v.get("value") and v["value"] not in names:
                        names.append(v["value"])
                for vs in (ent.get("aliases") or {}).values():
                    for v in vs or []:
                        if v.get("value") and v["value"] not in names:
                            names.append(v["value"])
                en = ((ent.get("labels") or {}).get("en") or (ent.get("labels") or {}).get("mul") or {}).get("value", "")
                got[real] = {"status": "ok", "label": en, "names": names}
                red = ent.get("redirects") or {}
                src = red.get("from") or (key if key != real else None)
                if src:
                    got[src] = {"status": "redirect", "redirect_to": red.get("to", real)}
            for q in batch:
                got.setdefault(q, {"status": "missing"})
            with self.path.open("a", encoding="utf-8") as fh:
                for q, r in got.items():
                    rec = {"qid": q, **r}
                    self.recs[q] = rec
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"  wd names {min(i + 50, len(todo))}/{len(todo)}", flush=True)
        return 0

    def _get(self, params: dict[str, str]) -> dict[str, Any]:
        delay = 5.0
        for attempt in range(9):
            time.sleep(max(0.0, 1.05 - (time.monotonic() - getattr(self, "_last", 0.0))))
            self._last = time.monotonic()
            try:
                resp = self.sess.get(API, params=params, timeout=90)
            except Exception:
                time.sleep(delay)
                delay = min(delay * 2, 120)
                continue
            self.requests += 1
            if resp.status_code in (429, 502, 503, 504):
                try:
                    pause = float(resp.headers.get("Retry-After", delay))
                except ValueError:
                    pause = delay
                time.sleep(min(max(pause, delay), 180))
                delay = min(delay * 2, 120)
                continue
            resp.raise_for_status()
            data = resp.json()
            if (data.get("error") or {}).get("code") == "maxlag":
                time.sleep(max(float(resp.headers.get("Retry-After", 5) or 5), delay))
                delay = min(delay * 2, 120)
                continue
            if data.get("error"):
                raise RuntimeError(f"Wikidata error: {data['error']}")
            return data
        raise RuntimeError("Wikidata kept throttling")

    def resolve(self, qid: str | None) -> str | None:
        seen: set[str] = set()
        while qid and qid not in seen:
            seen.add(qid)
            r = self.recs.get(qid) or {}
            if r.get("status") != "redirect":
                return qid
            qid = r.get("redirect_to")
        return qid

    def known(self, qid: str | None) -> bool:
        """Whether the QID's names are cached (an unfetched QID can't vouch for or against a name)."""
        r = self.recs.get(self.resolve(qid) or "")
        return bool(r) and r.get("status") in ("ok", "missing")

    def names(self, qid: str | None) -> list[str]:
        r = self.recs.get(self.resolve(qid) or "") or {}
        return r.get("names") or []


# ── inputs ───────────────────────────────────────────────────────────────────
def load_excluded() -> set[str]:
    out: set[str] = set()
    if MERGE_VERDICTS.exists():
        for r in csv.DictReader(MERGE_VERDICTS.open(encoding="utf-8")):
            for k in ("survivor_id", "loser_id"):
                if r.get(k):
                    out.add(r[k].strip())
    return out


def excluded(eid: str, merge_ids: set[str]) -> bool:
    return eid in merge_ids or eid.startswith(USER_DECISION_PREFIXES)


def load_pins() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    if PINS.exists():
        for r in csv.DictReader(PINS.open(encoding="utf-8")):
            if r.get("alias"):
                out.add((r["entity_id"], name_key(r["alias"])))
    return out


def load_ohm_verdicts() -> dict[str, dict[str, str]]:
    return {r["geo_ref_id"]: r for r in csv.DictReader(OHM_VERDICTS.open(encoding="utf-8"))}


def load_db(conn) -> tuple[list[dict], dict[str, dict], dict[str, list[dict]]]:
    cur = conn.cursor()
    cur.execute("""
        SELECT a.alias_id::text, a.entity_id::text, a.name, a.language, a.source, a.is_primary,
               a.created_at, a.updated_at
        FROM entity_aliases a ORDER BY a.created_at NULLS LAST, a.alias_id""")
    cols = ("alias_id", "entity_id", "name", "language", "source", "is_primary", "created_at", "updated_at")
    aliases = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.execute("SELECT entity_id::text, name, entity_type::text, wikidata_id FROM entities")
    entities = {r[0]: {"name": r[1], "type": r[2], "qid": r[3]} for r in cur.fetchall()}
    cur.execute("""
        SELECT entity_id::text, geo_ref_id::text, is_active, external_type::text, external_id,
               coalesce(source_meta->>'display_name', ''), coalesce(source_meta->>'type', ''),
               coalesce(external_tags, '{}'::jsonb)
        FROM entity_geo_refs WHERE retrieval_method = 'nominatim'""")
    refs: dict[str, list[dict]] = defaultdict(list)
    for eid, gid, active, xt, xid, dn, ftype, tags in cur.fetchall():
        refs[eid].append({"geo_ref_id": gid, "active": active, "ohm": f"{xt}/{xid}", "display_name": dn,
                          "match": dn.split(",")[0].strip(), "ftype": ftype, "tags": tags or {}})
    return aliases, entities, refs


# ── classification ───────────────────────────────────────────────────────────
def feature_is_thing(ref: dict) -> str:
    """'' or the OSM key/type that makes the feature a street, river, building …"""
    tags = ref["tags"]
    for k in THING_KEYS:
        if tags.get(k):
            return f"{k}={tags[k]}"
    if ref["ftype"] in THING_TYPES:
        return f"type={ref['ftype']}"
    return ""


def adds_kind_word(alias: str, entity_names: list[str]) -> str:
    """The kind word the alias adds to the entity's names ('Champa Street' ← 'Champa'), or ''."""
    toks = _name_tokens(alias)
    own = {t for n in entity_names for t in _name_tokens(n)}
    extra = [t for t in toks if t in KIND_WORDS and t not in own]
    return extra[0] if extra else ""


def shares_word(alias: str, entity_names: list[str]) -> bool:
    toks = {t for t in _name_tokens(alias) if len(t) > 2}
    return any(toks & {t for t in _name_tokens(n) if len(t) > 2} for n in entity_names)


def judge_ref(ref: dict, alias: str, ent: dict, qid_res: str | None, verdict: dict | None,
              wd: WDNames, own_names: list[str]) -> tuple[str, str]:
    """('right' | 'wrong' | 'unsure', evidence) for one Nominatim link whose match name is the alias."""
    tag = (ref["tags"].get("wikidata") or "").strip()
    if tag and qid_res and wd.resolve(tag) == qid_res:
        return "right", f"feature {ref['ohm']} carries the entity's QID {tag}"
    if verdict:
        v = verdict["verdict"]
        ev = f"OHM audit {v} ({verdict['reasons']}) on {ref['ohm']} '{ref['display_name'][:80]}'"
        return {"OK": "right", "WRONG": "wrong"}.get(v, "unsure"), ev
    thing = feature_is_thing(ref)
    kind = adds_kind_word(alias, own_names)
    base = f"{ref['ohm']} '{ref['display_name'][:80]}'"
    if tag and qid_res and wd.resolve(tag) != qid_res:
        return "wrong", f"feature carries another QID {tag}: {base}"
    if ent["type"] not in PLACE_TYPES and thing:
        return "wrong", f"feature is {thing} on a {ent['type']}: {base}"
    if kind:
        return "wrong", f"feature name adds '{kind}': {base}"
    if not shares_word(alias, own_names):
        return "unsure", f"feature name shares no word with the entity's names: {base}"
    return "unsure", f"unjudged link: {base}"


def classify(aliases: list[dict], entities: dict[str, dict], refs: dict[str, list[dict]],
             verdicts: dict[str, dict], wd: WDNames, merge_ids: set[str], pins: set[tuple[str, str]]
             ) -> tuple[list[dict], list[dict], Counter]:
    planned: list[dict] = []
    review: list[dict] = []
    stats: Counter = Counter()

    # primary-name index: name_key -> [(entity_id, resolved qid)]
    by_name: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
    for eid, e in entities.items():
        by_name[name_key(e["name"])].append((eid, wd.resolve(e["qid"]) if e["qid"] else None))
    seen_lower: dict[tuple[str, str], str] = {}

    def row(reason: str, a: dict, e: dict, evidence: str) -> dict:
        return {"reason": reason, "alias_id": a["alias_id"], "entity_id": a["entity_id"],
                "entity_name": e["name"], "entity_type": e["type"], "qid": e["qid"] or "",
                "alias": a["name"], "source": a["source"] or "", "created_at": str(a["created_at"] or ""),
                "evidence": evidence, "_a": a, "_e": e}

    for a in aliases:
        e = entities.get(a["entity_id"])
        if e is None:
            continue
        name = a["name"]
        lower_key = (a["entity_id"], name.strip().lower())
        first_same_case = seen_lower.setdefault(lower_key, name)
        if a["is_primary"]:
            stats["kept:is_primary"] += 1
            continue
        if (a["source"] or "") in PROTECTED_SOURCES or (a["entity_id"], name_key(name)) in pins:
            stats["kept:identity_audit"] += 1
            continue
        if excluded(a["entity_id"], merge_ids):
            stats["skipped:excluded_entity"] += 1
            continue
        if name.strip().lower() == e["name"].strip().lower():
            planned.append(row("same_as_name", a, e, "alias is the entity's own name (all lookups are case-insensitive)"))
            continue
        if first_same_case != name:
            planned.append(row("case_duplicate", a, e, f"same entity already has alias '{first_same_case}'"))
            continue

        qid_res = wd.resolve(e["qid"]) if e["qid"] else None
        own_wd = wd.names(qid_res) if qid_res else []
        wd_verified = any(same_name(name, n) for n in own_wd)
        own_names = [e["name"], *own_wd]

        def plan(reason: str, evidence: str, also: Iterable[str | None] = ()) -> None:
            """Plan the deletion, or hold it for review when a QID it rests on is unfetched."""
            unknown = [q for q in (e["qid"], *also) if q and not wd.known(q)]
            if unknown:
                stats[f"held:wikidata_unavailable:{reason}"] += 1
                review.append(row(f"held_wikidata_unavailable:{reason}", a, e,
                                  f"{evidence} || names of {', '.join(unknown)} not fetched"))
            else:
                planned.append(row(reason, a, e, evidence))

        manual = MANUAL_JUNK.get((a["entity_id"], name))
        if manual:
            plan("manual_junk", f"hand-checked: {manual}")
            continue
        keep_note = MANUAL_KEEP.get((a["entity_id"], name))
        if keep_note:
            stats["kept:manual"] += 1
            review.append(row("kept_manual", a, e, f"hand-checked keep: {keep_note}"))
            continue

        toks = [t for t in _name_tokens(name) if t != "the"]
        own_toks = [t for t in _name_tokens(e["name"]) if t != "the"]
        if len(toks) == 1 and toks[0] in GENERIC and own_toks != toks:  # 'The Monument' on Monument: its own name
            note =" (also a Wikidata alias of the QID, still too generic to match by)" if wd_verified else ""
            plan("generic_word", f"bare class noun '{toks[0]}'{note}")
            continue

        # Nominatim match names
        matches = [r for r in refs.get(a["entity_id"], []) if r["match"] and same_name(name, r["match"])]
        if matches:
            judged = [judge_ref(r, name, e, qid_res, verdicts.get(r["geo_ref_id"]), wd, own_names) for r in matches]
            kinds = {j[0] for j in judged}
            evidence = " | ".join(j[1] for j in judged)
            if wd_verified:
                stats["kept:nominatim_name_is_wikidata_name"] += 1
            elif "right" in kinds:
                stats["kept:nominatim_link_right"] += 1
            elif kinds == {"wrong"}:
                plan("nominatim_wrong_link", evidence)
            else:
                stats["kept:nominatim_link_unsure"] += 1
                review.append(row("nominatim_link_unsure", a, e, evidence))
            continue

        # Another row's primary name under another QID: listed, never deleted automatically —
        # most are a place's name in another era (Lugdunum/Lyon), a short form (Tryphon) or a
        # duplicate row (Liu Xie/Emperor Xian of Han); the clear junk is in MANUAL_JUNK.
        others = [(oid, oq) for oid, oq in by_name.get(name_key(name), []) if oid != a["entity_id"]]
        if others and qid_res:
            diff = [(oid, oq) for oid, oq in others if oq and oq != qid_res]
            if diff and not wd_verified:
                theirs = [(oid, oq) for oid, oq in diff if any(same_name(name, n) for n in wd.names(oq))]
                desc = "; ".join(f"{entities[oid]['name']} ({oq}, {oid[:8]})" for oid, oq in diff[:3])
                stats["kept:other_entity_name"] += 1
                review.append(row("other_entity_name", a, e, f"primary name of {desc}; a Wikidata name of "
                                  + ("theirs, not of " + qid_res if theirs else "neither")))
                continue
        stats["kept:other"] += 1
    return planned, review, stats


def needed_qids(aliases: list[dict], entities: dict[str, dict], refs: dict[str, list[dict]]) -> set[str]:
    """QIDs whose Wikidata names a decision can rest on: the entities of aliases that are a
    Nominatim match name, a bare class noun or another row's name; those other rows; the
    feature tags of the matched links; and every holder of such an alias (unmask guard)."""
    by_name: dict[str, list[str]] = defaultdict(list)
    for eid, e in entities.items():
        by_name[name_key(e["name"])].append(eid)
    holders: dict[str, set[str]] = defaultdict(set)
    for a in aliases:
        holders[a["name"].strip().lower()].add(a["entity_id"])
    out: set[str] = set()
    for a in aliases:
        e = entities.get(a["entity_id"])
        if not e:
            continue
        name = a["name"]
        matched = [r for r in refs.get(a["entity_id"], []) if r["match"] and same_name(name, r["match"])]
        toks = [t for t in _name_tokens(name) if t != "the"]
        others = [o for o in by_name.get(name_key(name), []) if o != a["entity_id"]]
        if not (matched or (len(toks) == 1 and toks[0] in GENERIC) or others):
            continue
        out.add(e["qid"])
        out |= {(r["tags"].get("wikidata") or "").strip() for r in matched}
        out |= {entities[o]["qid"] for o in others}
        out |= {entities[h]["qid"] for h in holders[name.strip().lower()]}
    return {q for q in out if q}


def unmask_guard(planned: list[dict], aliases: list[dict], entities: dict[str, dict], wd: WDNames,
                 merge_ids: set[str]) -> tuple[list[dict], list[dict]]:
    """Skip deletions that would leave an alias (case-insensitive) on exactly one other
    entity — the resolver would start linking it there — unless that holder's alias is
    a Wikidata name of its own QID. Iterates until stable."""
    holders: dict[str, set[str]] = defaultdict(set)
    for a in aliases:
        holders[a["name"].strip().lower()].add(a["alias_id"])
    by_id = {a["alias_id"]: a for a in aliases}
    keep = list(planned)
    skipped: list[dict] = []
    while True:
        dropped = {p["alias_id"] for p in keep}
        bad = []
        for p in keep:
            if p["reason"] in ("same_as_name", "case_duplicate"):
                continue  # the same entity keeps the name (as its name or another alias)
            key = p["alias"].strip().lower()
            left = [by_id[i] for i in holders[key] - dropped]
            left_entities = {x["entity_id"] for x in left}
            before = {by_id[i]["entity_id"] for i in holders[key]}
            if len(left_entities) == 1 and len(before) > 1 and p["entity_id"] not in left_entities:
                (oid,) = left_entities
                oe = entities[oid]
                verified = oe["qid"] and any(same_name(p["alias"], n) for n in wd.names(wd.resolve(oe["qid"])))
                if not verified:
                    bad.append((p, oid))
        if not bad:
            return keep, skipped
        bad_ids = {p["alias_id"] for p, _ in bad}
        for p, oid in bad:
            skipped.append({**p, "reason": f"skipped_unmasks:{p['reason']}",
                            "evidence": f"{p['evidence']} || deleting it leaves '{p['alias']}' only on "
                                        f"{entities[oid]['name']} ({oid[:8]}), unverified"})
        keep = [p for p in keep if p["alias_id"] not in bad_ids]


# ── output / apply ───────────────────────────────────────────────────────────
def write_rows(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def lit(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    return "'" + str(v).replace("'", "''") + "'"


def rollback_sql(rows: list[dict]) -> str:
    lines = ["-- Rollback of pipeline/audit/alias_cleanup.py (2026-11-01): re-insert the deleted aliases.",
             "-- Each insert is skipped when the alias row already exists or its entity is gone.",
             "BEGIN;"]
    for p in rows:
        a = p["_a"]
        lines.append(
            "INSERT INTO entity_aliases (alias_id, entity_id, name, language, source, is_primary, created_at, updated_at) "
            f"SELECT {lit(a['alias_id'])}, {lit(a['entity_id'])}, {lit(a['name'])}, {lit(a['language'])}, "
            f"{lit(a['source'])}, {lit(a['is_primary'])}, {lit(a['created_at'])}, {lit(a['updated_at'])} "
            f"WHERE EXISTS (SELECT 1 FROM entities WHERE entity_id = {lit(a['entity_id'])}) "
            f"AND NOT EXISTS (SELECT 1 FROM entity_aliases WHERE alias_id = {lit(a['alias_id'])});")
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def backup(out: Path) -> Path:
    path = out / f"entity_aliases-{time.strftime('%Y%m%d-%H%M%S')}.dump"
    with path.open("wb") as fh:
        subprocess.run([*COMPOSE, "exec", "-T", "db", "pg_dump", "-U", "history-mapped", "-Fc",
                        "-t", "public.entity_aliases", "history-mapped"], stdout=fh, check=True)
    if path.stat().st_size < 1000:
        raise SystemExit(f"backup {path} looks empty")
    return path


def apply(rows: list[dict], out: Path) -> list[dict]:
    bk = backup(out)
    print(f"backup: {bk}")
    (out / "rollback.sql").write_text(rollback_sql(rows), encoding="utf-8")
    applied = []
    conn = connect(read_only=False)
    with conn:
        cur = conn.cursor()
        for p in rows:
            a, e = p["_a"], p["_e"]
            cur.execute("""
                DELETE FROM entity_aliases x
                WHERE x.alias_id = %s AND x.entity_id = %s AND x.name = %s AND x.is_primary = false
                  AND x.source IS NOT DISTINCT FROM %s
                  AND EXISTS (SELECT 1 FROM entities e WHERE e.entity_id = x.entity_id
                              AND e.name = %s AND e.wikidata_id IS NOT DISTINCT FROM %s)""",
                        (a["alias_id"], a["entity_id"], a["name"], a["source"], e["name"], e["qid"]))
            status = "applied" if cur.rowcount == 1 else "skipped_changed"
            applied.append({**p, "status": status, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")})
    conn.close()
    return applied


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pipeline.audit.alias_cleanup")
    ap.add_argument("--apply", action="store_true", help="delete the planned aliases (after a backup)")
    ap.add_argument("--offline", action="store_true", help="Wikidata cache only")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    conn = connect(read_only=True)
    aliases, entities, refs = load_db(conn)
    conn.close()
    print(f"{len(aliases)} aliases on {len({a['entity_id'] for a in aliases})} entities; "
          f"{sum(len(v) for v in refs.values())} Nominatim refs")
    wd = WDNames(args.out / "cache", offline=args.offline)
    qids = needed_qids(aliases, entities, refs)
    missing = wd.fetch(qids)
    missing += wd.fetch({r.get("redirect_to") for r in list(wd.recs.values()) if r.get("status") == "redirect"})
    print(f"Wikidata names: {len(qids)} QIDs needed, {missing} unfetched ({wd.requests} requests)", flush=True)

    planned, review, stats = classify(aliases, entities, refs, load_ohm_verdicts(), wd, load_excluded(), load_pins())
    planned, skipped = unmask_guard(planned, aliases, entities, wd, load_excluded())
    review += skipped
    for p in planned:
        stats[f"planned:{p['reason']}"] += 1
    for s in skipped:
        stats[s["reason"]] += 1
    write_rows(args.out / "planned.csv", planned, PLANNED_FIELDS)
    write_rows(args.out / "review.csv", review, PLANNED_FIELDS)
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    print(f"planned {len(planned)} deletions -> {args.out / 'planned.csv'}; review {len(review)} -> {args.out / 'review.csv'}")
    langs = Counter(a["language"] for a in aliases)
    print(f"language values: {dict(langs)} (script/language check needs a language; none set)")
    if args.apply:
        applied = apply(planned, args.out)
        write_rows(args.out / "applied.csv", applied, ["ts", "status", *PLANNED_FIELDS])
        c = Counter(r["status"] for r in applied)
        print(f"applied: {dict(c)} -> {args.out / 'applied.csv'}; rollback: {args.out / 'rollback.sql'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
