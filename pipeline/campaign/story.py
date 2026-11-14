"""Narrative ("storyteller") chronicles: entity lookup and a pre-import check.

The overview chapters under `api/resources/chronicles/<slug>/chronicle.json`
are written by the `chapter-author` agent and imported with
`php artisan chronicles:import --all api/resources/chronicles`. These helpers
back two CLI commands:

- `entity-find`: the DB entities an entry can link, by name or Q-id.
- `chronicle-check`: the file's schema, the storyteller rules, and (with a DB)
  whether every linked entity resolves the way the importer will resolve it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from pydantic import ValidationError

from pipeline.agent.schemas.chronicle import Chronicle

ROLES = {"participant", "mentioned", "location", "outcome"}
SOURCE_TYPES = {"video_transcript", "article", "book_excerpt", "manual"}

ENTRIES_MIN, ENTRIES_MAX = 14, 30
NARRATIVE_MIN, NARRATIVE_MAX = 350, 1200
ENTITIES_MIN, ENTITIES_MAX = 1, 10
# A quotation longer than this many words is someone else's prose.
QUOTE_MAX_WORDS = 12
HARARI_MAX_ENTRIES = 3

QID = re.compile(r"^Q[1-9]\d*$")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
QUOTED = re.compile(r"[\"“”]([^\"“”]+)[\"“”]")
MARKDOWN = re.compile(r"(^|\n)\s*(#{1,6}\s|[-*•]\s|\d+\.\s)|\*\*|__|`")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _where(i: int) -> str:
    return f"entry {i}"


def check(data: Any, *, slug: str | None = None) -> Report:
    """Schema plus storyteller rules for one chronicle document (no DB)."""
    r = Report()
    try:
        chron = Chronicle.model_validate(data)
    except ValidationError as exc:
        for err in exc.errors()[:20]:
            loc = ".".join(str(p) for p in err["loc"])
            r.errors.append(f"schema: {loc}: {err['msg']}")
        return r

    if slug and chron.slug != slug:
        r.errors.append(f"slug {chron.slug!r} does not match its directory {slug!r}")
    if chron.status != "draft":
        r.errors.append(f"status must be 'draft' (a person publishes it), not {chron.status!r}")
    if chron.source_type not in SOURCE_TYPES:
        r.errors.append(f"source_type {chron.source_type!r} is not one of {sorted(SOURCE_TYPES)}")
    if not chron.source_reference:
        r.errors.append("source_reference is empty: say where the facts come from")
    if chron.start_year is None or chron.end_year is None:
        r.errors.append("the chronicle needs start_year and end_year")
    elif chron.end_year < chron.start_year:
        r.errors.append("end_year is before start_year")
    tags = data.get("tags") if isinstance(data, dict) else None
    if not tags:
        r.warnings.append("no tags: add era, region and theme slugs")

    n = len(chron.entries)
    if not ENTRIES_MIN <= n <= ENTRIES_MAX:
        r.errors.append(f"{n} entries; a chapter has {ENTRIES_MIN}-{ENTRIES_MAX}")
    orders = [e.sequence_order for e in chron.entries]
    if orders != list(range(n)):
        r.errors.append("sequence_order must run 0, 1, 2, … in file order")

    harari = 0
    previous: int | None = None
    for i, e in enumerate(chron.entries):
        at = _where(i)
        text = e.narrative_text.strip()
        if not NARRATIVE_MIN <= len(text) <= NARRATIVE_MAX:
            r.errors.append(f"{at}: narrative is {len(text)} characters; write {NARRATIVE_MIN}-{NARRATIVE_MAX}")
        if MARKDOWN.search(text):
            r.errors.append(f"{at}: narrative has markdown or a list; write plain prose")
        for quote in QUOTED.findall(text):
            if len(quote.split()) > QUOTE_MAX_WORDS:
                r.errors.append(f"{at}: a quotation of {len(quote.split())} words; quote at most {QUOTE_MAX_WORDS}")
        if "harari" in text.lower() or "sapiens" in text.lower():
            harari += 1
        if e.start_year is None:
            r.errors.append(f"{at}: start_year is missing")
        else:
            if e.end_year is not None and e.end_year < e.start_year:
                r.errors.append(f"{at}: end_year is before start_year")
            if chron.start_year is not None and chron.end_year is not None:
                last = e.end_year if e.end_year is not None else e.start_year
                if e.start_year < chron.start_year or last > chron.end_year:
                    r.warnings.append(
                        f"{at}: {e.start_year}..{last} falls outside the chapter's "
                        f"{chron.start_year}..{chron.end_year}; never re-date a fact, move it or widen the span")
            if previous is not None and e.start_year < previous:
                r.warnings.append(f"{at}: starts before the entry above it ({e.start_year} < {previous})")
            previous = e.start_year
        if not (e.source_evidence or "").strip():
            r.errors.append(f"{at}: source_evidence is empty; list the Wikipedia articles the facts come from")

        ents = e.secondary_entities
        if not ENTITIES_MIN <= len(ents) <= ENTITIES_MAX:
            r.errors.append(f"{at}: {len(ents)} entities; link {ENTITIES_MIN}-{ENTITIES_MAX}")
        seen: set[str] = set()
        for ent in ents:
            label = ent.name or ent.entity_id
            if ent.role not in ROLES:
                r.errors.append(f"{at}: {label}: role {ent.role!r} is not one of {sorted(ROLES)}")
            if ent.wikidata_id and not QID.match(ent.wikidata_id):
                r.errors.append(f"{at}: {label}: wikidata_id {ent.wikidata_id!r} is not a Q-id")
            if not UUID.match(ent.entity_id) and not ent.wikidata_id:
                r.errors.append(f"{at}: {label}: needs the entity_id (uuid) or wikidata_id from entity-find")
            if not ent.name:
                r.errors.append(f"{at}: {ent.entity_id}: needs its name")
            key = ent.wikidata_id or ent.entity_id
            if key in seen:
                r.errors.append(f"{at}: {label} is linked twice")
            seen.add(key)

    if harari > HARARI_MAX_ENTRIES:
        r.warnings.append(
            f"{harari} entries name Harari or Sapiens; keep it to {HARARI_MAX_ENTRIES} attributed mentions")
    return r


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def names_agree(a: str, b: str) -> bool:
    """Loose match: one name's words are all among the other's."""
    wa, wb = set(_norm(a).split()), set(_norm(b).split())
    return bool(wa and wb) and (wa <= wb or wb <= wa)


def resolve(conn, data: dict) -> Report:
    """How each linked entity resolves against the DB (uuid, then Q-id)."""
    r = Report()
    refs: list[tuple[int, dict]] = [
        (i, ent)
        for i, entry in enumerate(data.get("entries", []))
        for ent in entry.get("secondary_entities", [])
    ]
    qids = sorted({ent.get("wikidata_id") for _, ent in refs if ent.get("wikidata_id")})
    uuids = sorted({ent["entity_id"] for _, ent in refs if UUID.match(str(ent.get("entity_id", "")))})
    by_qid: dict[str, tuple[str, str]] = {}
    by_id: dict[str, tuple[str, str | None]] = {}
    with conn.cursor() as cur:
        if qids:
            cur.execute(
                "select wikidata_id, entity_id::text, name from entities where wikidata_id = any(%s)", (qids,))
            for qid, eid, name in cur.fetchall():
                by_qid[qid] = (eid, name)
        if uuids:
            cur.execute(
                "select entity_id::text, name, wikidata_id from entities where entity_id::text = any(%s)", (uuids,))
            for eid, name, qid in cur.fetchall():
                by_id[eid] = (name, qid)

    for i, ent in refs:
        at, label = _where(i), ent.get("name") or ent.get("entity_id")
        eid, qid = str(ent.get("entity_id", "")), ent.get("wikidata_id")
        if eid in by_id:
            name, db_qid = by_id[eid]
            if qid and db_qid and qid != db_qid:
                r.errors.append(f"{at}: {label}: entity_id is {name} ({db_qid}), not {qid}")
            continue
        if UUID.match(eid):
            r.errors.append(f"{at}: {label}: entity_id {eid} is not in the database")
            continue
        if qid in by_qid:
            db_id, db_name = by_qid[qid]
            if not names_agree(label or "", db_name):
                r.warnings.append(f"{at}: {label} ({qid}) is {db_name!r} in the database; check the Q-id")
            r.warnings.append(f"{at}: {label}: set entity_id to {db_id}")
            continue
        r.errors.append(
            f"{at}: {label} ({qid}) is not in the database; link another entity or drop it (list it in notes.md)")
    return r


def find(conn, terms: Iterable[str], limit: int = 6) -> list[tuple[str, list[tuple]]]:
    """Entities whose name or alias matches each term (or whose Q-id is it)."""
    out: list[tuple[str, list[tuple]]] = []
    with conn.cursor() as cur:
        for term in terms:
            term = term.strip()
            if QID.match(term):
                cur.execute(
                    "select e.entity_id::text, e.name, e.entity_type::text, e.wikidata_id, coalesce(e.summary, '') "
                    "from entities e where e.wikidata_id = %s", (term,))
            else:
                cur.execute(
                    """
                    select e.entity_id::text, e.name, e.entity_type::text, e.wikidata_id, coalesce(e.summary, '')
                    from entities e
                    where e.name ilike %(like)s
                       or exists (select 1 from entity_aliases a
                                  where a.entity_id = e.entity_id and a.name ilike %(like)s)
                    order by (lower(e.name) = lower(%(term)s)) desc,
                             (e.name ilike %(prefix)s) desc,
                             e.impact_score desc nulls last,
                             length(e.name)
                    limit %(limit)s
                    """,
                    {"like": f"%{term}%", "prefix": f"{term}%", "term": term, "limit": limit},
                )
            out.append((term, cur.fetchall()))
    return out
