"""Operations on a candidates.json handoff held as a plain dict.

Every item written passes the real pipeline models (ParsedEvent / CandidateEntity /
CandidateRelation) plus the gate's type lists, so a handoff edited only through
these functions stays loadable by validate_handoff and --from-candidates.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

from pydantic import ValidationError

from pipeline.agent.graph.nodes.validate import ALLOWED_RELATION_TYPES
from pipeline.agent.schemas.entities import (
    CandidateEntity,
    ParsedEvent,
    _CANONICAL_ENTITY_TYPES,
)
from pipeline.agent.schemas.relations import CandidateRelation
from pipeline.agent.validate_handoff import ERA_BOUNDS, _year
from pipeline.campaign.dates import depad, jan1_years
from pipeline.campaign.labels import CODE as AMBIGUOUS_LABEL, ambiguous_label

PARTS = {
    "events": "parsed_events",
    "entities": "candidate_entities",
    "relations": "candidate_relations",
    "summaries": "summaries",
}
MODELS = {"events": ParsedEvent, "entities": CandidateEntity, "relations": CandidateRelation}
FIELDS = {part: set(model.model_fields) for part, model in MODELS.items()}
# Campaign-only bookkeeping on events: `fact` = the transcript fact number the event
# was extracted from (the join key for `handoff slice` / `rm-slice` / `check --facts`).
# ParsedEvent ignores unknown keys (pydantic extra='ignore'), so load_handoff, the
# validator and the graph never see it.
FIELDS["events"] |= {"fact"}
SUMMARY_FIELDS = {"label", "summary", "significance"}
TOP_ORDER = [
    "run_id", "source_transcript", "title", "summaries_precomputed", "parsed_events",
    "candidate_entities", "candidate_relations", "summaries", "self_audit",
]
DATE_RE = re.compile(r"^-?\d{1,5}(-\d{2}(-\d{2})?)?$")
MIN_DENSITY = 1.3
MIN_ENTITIES_PER_EVENT = 1.5
MIN_EVENTS_PER_FACT = 0.8
SLICE_REL_PER_FACT = 2.0
SLICE_REL_PER_NEW_ENTITY = 1.5
SINGULAR = {"events": "event", "entities": "entity", "relations": "relation"}

# Severities: E blocks add and fails check; A blocks add but is only a warning in
# check (authoring-time strictness the validator doesn't enforce); W never blocks.
Problem = tuple[str, str, str]


class OpError(Exception):
    pass


# ── file I/O ────────────────────────────────────────────────────────────────

def _j(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def dump_doc(doc: dict) -> str:
    """One item per line: diff- and grep-friendly, never needs a full `cat`."""
    keys = [k for k in TOP_ORDER if k in doc] + [k for k in doc if k not in TOP_ORDER]
    out = []
    for k in keys:
        v = doc[k]
        if isinstance(v, list) and v:
            body = ",\n".join("    " + _j(item) for item in v)
            out.append(f"  {_j(k)}: [\n{body}\n  ]")
        elif isinstance(v, dict) and v:
            body = ",\n".join(f"    {_j(kk)}: {_j(vv)}" for kk, vv in v.items())
            out.append(f"  {_j(k)}: {{\n{body}\n  }}")
        else:
            out.append(f"  {_j(k)}: {_j(v)}")
    return "{\n" + ",\n".join(out) + "\n}\n"


def load_doc(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_doc(path: Path, doc: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(dump_doc(doc), encoding="utf-8")
    os.replace(tmp, path)


@contextmanager
def locked(directory: Path) -> Iterator[None]:
    fd = os.open(directory, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def new_doc(run_id: str, source_transcript: str, title: str) -> dict:
    return {
        "run_id": run_id,
        "source_transcript": source_transcript,
        "title": title,
        "summaries_precomputed": True,
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "summaries": {},
    }


def counts(doc: dict) -> dict[str, int]:
    return {part: len(doc.get(key) or []) for part, key in PARTS.items()}


def counts_line(doc: dict) -> str:
    return " ".join(f"{k}={v}" for k, v in counts(doc).items())


# ── keys ────────────────────────────────────────────────────────────────────

def item_key(part: str, item: dict) -> Any:
    if part == "relations":
        return (item.get("source_label"), item.get("relationship_type"), item.get("target_label"))
    return item.get("label")


def rel_key_str(key: tuple) -> str:
    return "|".join(str(k) for k in key)


def parse_rel_key(text: str) -> tuple[str, str, str]:
    parts = [p.strip() for p in text.split("|")]
    if len(parts) != 3 or not all(parts):
        raise OpError(f"relation key must be SOURCE|TYPE|TARGET, got {text!r}")
    return parts[0], parts[1], parts[2]


def display(part: str, item: dict) -> str:
    key = item_key(part, item)
    return rel_key_str(key) if part == "relations" else str(key or "?")


# ── item validation ─────────────────────────────────────────────────────────

@dataclass
class Ctx:
    events: set[str]
    entities: set[str]
    era: str | None = None
    # Transcript facts {number: line} (None = transcript unknown), each event's fact
    # number, and the years some fact states "1 January <year>" for explicitly.
    fact_text: dict[int, str] | None = None
    event_facts: dict[str, int] = field(default_factory=dict)
    jan1_years: frozenset[int] = frozenset()

    @classmethod
    def from_doc(cls, doc: dict, era: str | None, fact_map: dict[int, str] | None = None) -> "Ctx":
        events = [e for e in doc.get("parsed_events") or [] if isinstance(e, dict)]
        return cls(
            events={e.get("label") for e in events},
            entities={e.get("label") for e in doc.get("candidate_entities") or []},
            era=era if era in ERA_BOUNDS else None,
            fact_text=fact_map,
            event_facts={e.get("label"): n for e in events if (n := _fact_number(e.get("fact"))) is not None},
            jan1_years=frozenset(jan1_years(fact_map.values())) if fact_map else frozenset(),
        )

    def register(self, part: str, item: dict) -> None:
        if part == "events":
            self.events.add(item["label"])
            if _fact_number(item.get("fact")) is not None:
                self.event_facts[item["label"]] = _fact_number(item["fact"])
        elif part == "entities":
            self.entities.add(item["label"])

    def fact_of(self, part: str, item: dict) -> int | None:
        """The transcript fact an item comes from: an event's own `fact`, else its
        source_event's."""
        if part == "events":
            return _fact_number(item.get("fact"))
        return self.event_facts.get(item.get("source_event"))

    def padded_dates(self, part: str, item: dict) -> list[tuple[str, str, str, int | None]]:
        """(field, value, fix, fact) for each start/end date padded to -01-01 that no
        transcript fact backs with "1 January <year>" (see pipeline.campaign.dates)."""
        n = self.fact_of(part, item)
        text = (self.fact_text or {}).get(n) if n is not None else None
        out = []
        for f in ("start_date", "end_date"):
            fix = depad(item.get(f), text, self.jan1_years)
            if fix is not None:
                out.append((f, item[f], fix, n))
        return out


def _padded_msg(f: str, old: str, new: str, n: int | None) -> str:
    where = f"fact {n}" if n is not None else "its fact"
    return f"{f} {old!r} -> {new!r} ({where} states no 1 January; never pad a year or month to -01-01)"


def _strip(part: str, item: dict) -> dict:
    out = dict(item)
    for k, v in out.items():
        if isinstance(v, str) and k != "description":
            out[k] = v.strip()
    for k in ("aliases", "mentioned_entities"):
        if isinstance(out.get(k), list):
            out[k] = [s.strip() if isinstance(s, str) else s for s in out[k]]
    return out


def _fmt_validation(exc: ValidationError) -> list[str]:
    return [f"{'.'.join(str(x) for x in e['loc']) or 'item'}: {e['msg']}" for e in exc.errors()]


def _fact_number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    return value if isinstance(value, int) and value >= 1 else None


def _date_problems(item: dict) -> list[Problem]:
    probs: list[Problem] = []
    for f in ("start_date", "end_date"):
        v = item.get(f)
        if v is not None and not DATE_RE.match(v):
            probs.append(("E", "date-format",
                          f"{f} {v!r} must be a year string like '-331' (BCE negative), '1453', '1896-03' or '1896-03-14'"))
    sy, ey = _year(item.get("start_date")), _year(item.get("end_date"))
    if sy is not None and ey is not None and sy > ey:
        probs.append(("E", "start>end", f"start {sy} > end {ey}"))
    for y in (sy, ey):
        if y is not None and not -10000 < y <= 2100:
            probs.append(("E", "implausible-year", f"implausible year {y}"))
    return probs


def check_item(part: str, item: Any, ctx: Ctx) -> tuple[dict | None, list[Problem]]:
    """Validate one events/entities/relations item; returns (clean dump, problems)."""
    if not isinstance(item, dict):
        return None, [("E", "schema", "item is not a JSON object")]
    probs: list[Problem] = []
    unknown = sorted(set(item) - FIELDS[part])
    if unknown:
        hint = " (summaries go in via `handoff add RUN summaries`)" if {"summary", "significance"} & set(unknown) else ""
        probs.append(("E", "unknown-field",
                      f"unknown field(s) {', '.join(unknown)}; allowed: {', '.join(sorted(FIELDS[part]))}{hint}"))
    fact = None
    if part == "events" and item.get("fact") is not None:
        fact = _fact_number(item["fact"])
        if fact is None:
            probs.append(("E", "fact", f"fact {item['fact']!r} must be the transcript fact number (a positive integer)"))
    try:
        clean = MODELS[part].model_validate(item).model_dump()
    except ValidationError as exc:
        return None, probs + [("E", "schema", m) for m in _fmt_validation(exc)]
    if fact is not None:
        clean["fact"] = fact

    if part in ("events", "entities") and not clean["label"]:
        probs.append(("E", "schema", "label is empty"))
    probs += _date_problems(clean)
    for f, old, new, n in ctx.padded_dates(part, clean):
        probs.append(("E", "padded-date", f"{_padded_msg(f, old, new, n)}; fix: `handoff fix-dates RUN --apply`"))

    if part == "events" and ctx.era:
        lo, hi = ERA_BOUNDS[ctx.era]
        y = _year(clean.get("start_date"))
        if y is not None and not lo <= y <= hi:
            probs.append(("E", "era-bounds", f"start year {y} outside {ctx.era} bounds [{lo}, {hi}]"))

    elif part == "entities":
        raw_type = item.get("entity_type")
        if clean["entity_type"] not in _CANONICAL_ENTITY_TYPES:
            probs.append(("E", "entity-type",
                          f"entity_type {raw_type!r} is not canonical (see `python -m pipeline.campaign types`)"))
        elif raw_type != clean["entity_type"]:
            probs.append(("W", "type-normalized", f"entity_type {raw_type!r} -> {clean['entity_type']!r}"))
        if clean.get("source_event") and clean["source_event"] not in ctx.events:
            probs.append(("A", "source-event",
                          f"source_event {clean['source_event']!r} is not an event label (add the event first or use null)"))
        if clean.get("wikidata_id"):
            probs.append(("A", "wikidata-id", "wikidata_id must stay null (resolution is the pipeline's job)"))
        # 'Philip II' links to whichever namesake the DB holds (pipeline.campaign.labels).
        why = ambiguous_label(clean["label"], clean["entity_type"])
        if why:
            probs.append(("W", AMBIGUOUS_LABEL, why))

    elif part == "relations":
        if clean["relationship_type"] not in ALLOWED_RELATION_TYPES:
            probs.append(("E", "relation-type",
                          f"relationship_type {clean['relationship_type']!r} not allowed (see `python -m pipeline.campaign types`)"))
        for end in ("source_label", "target_label"):
            if clean[end] not in ctx.entities:
                probs.append(("E", "dangling-endpoint",
                              f"{end.split('_')[0]} {clean[end]!r} is not an entity label (add the entity first)"))
        if clean["source_label"].casefold() == clean["target_label"].casefold():
            probs.append(("E", "self-relation", "source and target are the same entity"))
        if clean.get("source_event") and clean["source_event"] not in ctx.events:
            probs.append(("A", "source-event",
                          f"source_event {clean['source_event']!r} is not an event label (add the event first or use null)"))
    return clean, probs


def check_summary(label: str, fields: Any, ctx: Ctx) -> tuple[dict | None, list[Problem]]:
    if not isinstance(fields, dict):
        return None, [("E", "schema", "summary entry must be an object with summary + significance")]
    probs: list[Problem] = []
    unknown = sorted(set(fields) - SUMMARY_FIELDS)
    if unknown:
        probs.append(("E", "unknown-field", f"unknown field(s) {', '.join(unknown)}; allowed: summary, significance"))
    clean = {}
    for f in ("summary", "significance"):
        v = fields.get(f)
        if not isinstance(v, str) or not v.strip():
            probs.append(("E", "summary-empty", f"{f} must be a non-empty string"))
        else:
            clean[f] = v.strip()
    if not label:
        probs.append(("E", "schema", "label is empty"))
    elif label not in ctx.entities:
        probs.append(("A", "summary-orphan", f"no entity labelled {label!r} (add the entity first)"))
    return clean, probs


# ── upsert ──────────────────────────────────────────────────────────────────

@dataclass
class AddResult:
    added: int = 0
    updated: int = 0
    rejected: list[tuple[int, str, str]] = field(default_factory=list)
    notes: list[tuple[int, str, str]] = field(default_factory=list)
    # Non-blocking label advice (ambiguous-label): the item IS written.
    hints: list[tuple[int, str, str]] = field(default_factory=list)


def _summary_items(payload: Any) -> list[tuple[str, Any]]:
    if isinstance(payload, dict):
        if {"label", "summary"} <= set(payload):
            payload = [payload]
        else:
            return [(str(k).strip(), v) for k, v in payload.items()]
    if not isinstance(payload, list):
        raise OpError("summaries payload must be an object map {label: {summary, significance}} or an array")
    out = []
    for item in payload:
        if isinstance(item, dict):
            rest = {k: v for k, v in item.items() if k != "label"}
            out.append((str(item.get("label") or "").strip(), rest))
        else:
            out.append(("", item))
    return out


def upsert(doc: dict, part: str, payload: Any, *, era: str | None = None,
           replace: bool = False, fact_map: dict[int, str] | None = None) -> AddResult:
    """Insert or update items by key. Updates merge given fields over the stored
    item (explicit null clears a field) unless replace=True. A date padded to
    -01-01 that its fact (fact_map) doesn't state is written as the year (or
    year-month) instead, with a note."""
    res = AddResult()
    ctx = Ctx.from_doc(doc, era, fact_map)

    if part == "summaries":
        store = doc.setdefault("summaries", {})
        for i, (label, fields) in enumerate(_summary_items(payload)):
            exists = label in store
            merged = fields
            if exists and not replace and isinstance(fields, dict):
                merged = {**store[label], **fields}
            clean, probs = check_summary(label, merged, ctx)
            blocking = [m for s, _, m in probs if s in ("E", "A")]
            if blocking:
                res.rejected.append((i, label or "?", "; ".join(blocking)))
                continue
            store[label] = clean
            res.updated += exists
            res.added += not exists
        return res

    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise OpError(f"{part} payload must be a JSON array of objects")
    items = doc.setdefault(PARTS[part], [])
    index: dict[Any, int] = {}
    for pos, it in enumerate(items):
        index.setdefault(item_key(part, it), pos)

    for i, raw in enumerate(payload):
        if not isinstance(raw, dict):
            res.rejected.append((i, "?", "item is not a JSON object"))
            continue
        raw = _strip(part, raw)
        key = item_key(part, raw)
        pos = index.get(key)
        merged = raw if pos is None or replace else {**items[pos], **raw}
        depadded = ctx.padded_dates(part, merged)
        merged = {**merged, **{f: new for f, _, new, _ in depadded}}
        clean, probs = check_item(part, merged, ctx)
        label = display(part, raw)
        blocking = [m for s, _, m in probs if s in ("E", "A")]
        if blocking or clean is None:
            res.rejected.append((i, label, "; ".join(blocking)))
            continue
        res.notes += [(i, label, m) for s, c, m in probs if s == "W" and c != AMBIGUOUS_LABEL]
        res.hints += [(i, label, f"{c}: {m}") for s, c, m in probs if c == AMBIGUOUS_LABEL]
        res.notes += [(i, label, f"padded-date {_padded_msg(*d)}") for d in depadded]
        if pos is None:
            items.append(clean)
            index[key] = len(items) - 1
            res.added += 1
        else:
            items[pos] = clean
            res.updated += 1
        ctx.register(part, clean)
    return res


def fix_padded_dates(doc: dict, fact_map: dict[int, str] | None) -> list[str]:
    """Rewrite every start/end date padded to -01-01 that no transcript fact backs
    (events, entities, relations) to its year or year-month. Returns one line per fix."""
    ctx = Ctx.from_doc(doc, None, fact_map)
    report: list[str] = []
    for part in ("events", "entities", "relations"):
        for item in doc.get(PARTS[part]) or []:
            if not isinstance(item, dict):
                continue
            for f, old, new, n in ctx.padded_dates(part, item):
                item[f] = new
                report.append(f"{SINGULAR[part]} {display(part, item)!r}: {_padded_msg(f, old, new, n)}")
    return report


# ── rm / rename ─────────────────────────────────────────────────────────────

def remove(doc: dict, part: str, keys: Iterable[str]) -> tuple[list[str], list[str]]:
    """Remove items; returns (report lines, keys not found). Entity removal
    cascades to its relations + summary; event removal clears source_event refs."""
    report: list[str] = []
    missing: list[str] = []
    events = doc.setdefault("parsed_events", [])
    entities = doc.setdefault("candidate_entities", [])
    relations = doc.setdefault("candidate_relations", [])
    summaries = doc.setdefault("summaries", {})

    for raw_key in keys:
        if part == "relations":
            key = parse_rel_key(raw_key)
            keep = [r for r in relations if item_key("relations", r) != key]
            if len(keep) == len(relations):
                missing.append(raw_key)
                continue
            report.append(f"removed relation {rel_key_str(key)}" + (
                f" x{len(relations) - len(keep)}" if len(relations) - len(keep) > 1 else ""))
            relations[:] = keep

        elif part == "entities":
            label = raw_key.strip()
            if not any(e.get("label") == label for e in entities):
                missing.append(raw_key)
                continue
            entities[:] = [e for e in entities if e.get("label") != label]
            gone = [r for r in relations if label in (r.get("source_label"), r.get("target_label"))]
            gone_ids = {id(r) for r in gone}
            relations[:] = [r for r in relations if id(r) not in gone_ids]
            report.append(f"removed entity {label!r}")
            for r in gone:
                report.append(f"  cascaded relation {display('relations', r)}")
            if summaries.pop(label, None) is not None:
                report.append("  cascaded summary")

        elif part == "events":
            label = raw_key.strip()
            if not any(e.get("label") == label for e in events):
                missing.append(raw_key)
                continue
            events[:] = [e for e in events if e.get("label") != label]
            report.append(f"removed event {label!r}")
            n_ent = n_rel = 0
            for e in entities:
                if e.get("source_event") == label:
                    e["source_event"] = None
                    n_ent += 1
            for r in relations:
                if r.get("source_event") == label:
                    r["source_event"] = None
                    n_rel += 1
            if n_ent or n_rel:
                report.append(f"  cleared source_event on {n_ent} entities, {n_rel} relations")
        else:
            raise OpError(f"cannot rm from {part!r}")
    return report, missing


def _repoint_relations(relations: list[dict], old: str, new: str) -> list[str]:
    """Rewrite endpoints old -> new; drop only the rewritten relations that turn
    into self-relations or collide with an existing triple."""
    touched: set[int] = set()
    n = 0
    for r in relations:
        for end in ("source_label", "target_label"):
            if r.get(end) == old:
                r[end] = new
                n += 1
                touched.add(id(r))
    seen = {item_key("relations", r) for r in relations if id(r) not in touched}
    keep, report = [], [f"  repointed {n} relation endpoint(s)"]
    for r in relations:
        key = item_key("relations", r)
        if id(r) in touched:
            if r.get("source_label") == r.get("target_label"):
                report.append(f"  dropped self-relation {rel_key_str(key)}")
                continue
            if key in seen:
                report.append(f"  dropped duplicate relation {rel_key_str(key)}")
                continue
            seen.add(key)
        keep.append(r)
    relations[:] = keep
    return report


def rename_entity(doc: dict, old: str, new: str, merge: bool = False) -> list[str]:
    old, new = old.strip(), new.strip()
    if not new or old == new:
        raise OpError("new label must be non-empty and different")
    entities = doc.setdefault("candidate_entities", [])
    src = next((e for e in entities if e.get("label") == old), None)
    if src is None:
        raise OpError(f"no entity labelled {old!r}")
    dst = next((e for e in entities if e.get("label") == new), None)
    if dst is not None and not merge:
        raise OpError(f"entity {new!r} already exists; pass --merge to fold {old!r} into it")

    report = []
    summaries = doc.setdefault("summaries", {})
    if dst is None:
        src["label"] = new
        report.append(f"renamed entity {old!r} -> {new!r}")
        if old in summaries:
            summaries[new] = summaries.pop(old)
            report.append("  moved summary")
    else:
        aliases = list(dst.get("aliases") or [])
        for a in [old, *(src.get("aliases") or [])]:
            if a != new and a not in aliases:
                aliases.append(a)
        dst["aliases"] = aliases
        entities[:] = [e for e in entities if e is not src]
        report.append(f"merged entity {old!r} into {new!r} (aliases now {aliases})")
        old_summary = summaries.pop(old, None)
        if old_summary and not (summaries.get(new) or {}).get("summary"):
            summaries[new] = old_summary
            report.append("  kept merged entity's summary (target had none)")

    report += _repoint_relations(doc.setdefault("candidate_relations", []), old, new)

    m = 0
    for ev in doc.get("parsed_events") or []:
        mentioned = ev.get("mentioned_entities") or []
        if old in mentioned:
            ev["mentioned_entities"] = list(dict.fromkeys(new if x == old else x for x in mentioned))
            m += 1
    if m:
        report.append(f"  updated mentioned_entities in {m} event(s)")
    return report


def rename_event(doc: dict, old: str, new: str, merge: bool = False) -> list[str]:
    old, new = old.strip(), new.strip()
    if not new or old == new:
        raise OpError("new label must be non-empty and different")
    events = doc.setdefault("parsed_events", [])
    src = next((e for e in events if e.get("label") == old), None)
    if src is None:
        raise OpError(f"no event labelled {old!r}")
    exists = any(e.get("label") == new for e in events)
    if exists and not merge:
        raise OpError(f"event {new!r} already exists; pass --merge to fold {old!r} into it")
    if exists:
        events[:] = [e for e in events if e is not src]
        report = [f"merged event {old!r} into {new!r}"]
    else:
        src["label"] = new
        report = [f"renamed event {old!r} -> {new!r}"]
    n_ent = n_rel = 0
    for e in doc.get("candidate_entities") or []:
        if e.get("source_event") == old:
            e["source_event"] = new
            n_ent += 1
    for r in doc.get("candidate_relations") or []:
        if r.get("source_event") == old:
            r["source_event"] = new
            n_rel += 1
    report.append(f"  repointed source_event on {n_ent} entities, {n_rel} relations")
    return report


# ── fact slices ─────────────────────────────────────────────────────────────

def parse_facts(spec: str) -> list[int]:
    """'21-40' / '5' / '1-20,45,47-49' -> sorted unique fact numbers."""
    out: set[int] = set()
    for chunk in (spec or "").split(","):
        m = re.fullmatch(r"\s*(\d+)\s*(?:[-–]\s*(\d+)\s*)?", chunk)
        lo, hi = (int(m.group(1)), int(m.group(2) or m.group(1))) if m else (0, -1)
        if not m or lo < 1 or hi < lo:
            raise OpError(f"--facts must look like 21-40 or 5,7-9 (numbers >= 1), got {spec!r}")
        out.update(range(lo, hi + 1))
    return sorted(out)


def fmt_facts(nums: Iterable[int]) -> str:
    """[1,2,3,7,9,10] -> '1-3,7,9-10'."""
    runs: list[list[int]] = []
    for n in sorted(set(nums)):
        if runs and n == runs[-1][1] + 1:
            runs[-1][1] = n
        else:
            runs.append([n, n])
    return ",".join(str(a) if a == b else f"{a}-{b}" for a, b in runs)


@dataclass
class SliceScope:
    """What a fact slice owns: its events (by `fact`), the entities first mentioned
    in them (`source_event`) and the relations they produced (`source_event`)."""
    facts: list[int]
    events: set[str]
    entities: set[str]

    def owns(self, part: str, item: dict) -> bool:
        if part == "events":
            return item.get("label") in self.events
        if part == "entities":
            return item.get("label") in self.entities
        return item.get("source_event") in self.events


def slice_scope(doc: dict, facts: Iterable[int]) -> SliceScope:
    wanted = set(facts)
    events = {e.get("label") for e in doc.get("parsed_events") or []
              if isinstance(e, dict) and e.get("fact") in wanted}
    entities = {e.get("label") for e in doc.get("candidate_entities") or []
                if isinstance(e, dict) and e.get("source_event") in events}
    return SliceScope(sorted(wanted), events, entities)


def _fact_order(event: dict) -> tuple[bool, int]:
    return event.get("fact") is None, event.get("fact") or 0


def remove_slice(doc: dict, facts: Iterable[int]) -> list[str]:
    """Undo a slice's extraction so it can be redone without duplicates: drop its
    events and the relations they produced; drop the entities first mentioned there
    unless another slice still uses them (relation endpoint or mentioned_entities),
    in which case their source_event moves to the earliest remaining mention."""
    scope = slice_scope(doc, facts)
    span = fmt_facts(scope.facts)
    events = doc.setdefault("parsed_events", [])
    entities = doc.setdefault("candidate_entities", [])
    relations = doc.setdefault("candidate_relations", [])
    summaries = doc.setdefault("summaries", {})
    if not scope.events:
        untagged = sum(1 for e in events if isinstance(e, dict) and e.get("fact") is None)
        return [f"rm-slice {span}: no event carries these fact numbers; nothing removed"
                + (f" ({untagged} events have no fact number)" if untagged else "")]

    kept_events = [e for e in events if e.get("label") not in scope.events]
    kept_rels = [r for r in relations if r.get("source_event") not in scope.events]
    first_mention: dict[str, str] = {}
    for ev in sorted(kept_events, key=_fact_order):
        for label in ev.get("mentioned_entities") or []:
            first_mention.setdefault(label, ev.get("label"))
    rel_event: dict[str, str] = {}
    for r in kept_rels:
        for end in ("source_label", "target_label"):
            if r.get("source_event"):
                rel_event.setdefault(r.get(end), r["source_event"])

    kept_ents, dropped, repointed = [], [], []
    for e in entities:
        label = e.get("label")
        if label not in scope.entities:
            kept_ents.append(e)
        elif label in first_mention or label in rel_event:
            e["source_event"] = first_mention.get(label) or rel_event.get(label)
            kept_ents.append(e)
            repointed.append(label)
        else:
            dropped.append(label)
    n_sum = sum(summaries.pop(label, None) is not None for label in dropped)
    report = [f"rm-slice {span}: removed events={len(events) - len(kept_events)} "
              f"relations={len(relations) - len(kept_rels)} entities={len(dropped)} summaries={n_sum}"]
    if repointed:
        report.append(f"  kept {len(repointed)} entities still used by other facts (source_event moved): "
                      + "; ".join(repointed[:15]) + (" ..." if len(repointed) > 15 else ""))
    events[:], relations[:], entities[:] = kept_events, kept_rels, kept_ents
    return report


def slice_lines(doc: dict | None, fact_map: dict[int, str], facts: list[int], transcript: str) -> list[str]:
    """Everything an extraction worker needs for one slice, without the whole
    transcript or handoff: the facts verbatim, events already tagged with them, and
    every existing entity label grouped by type."""
    present = [n for n in facts if n in fact_map]
    out = [f"# facts {fmt_facts(facts)} of {len(fact_map)} ({transcript})"]
    out += [fact_map[n] for n in present]
    absent = [n for n in facts if n not in fact_map]
    if absent:
        out.append(f"(not in transcript: {fmt_facts(absent)})")
    if doc is None:
        out.append("# no handoff yet: slice 1 starts with `handoff init RUN --title ... --force`")
        return out
    wanted = set(facts)
    tagged = sorted((e for e in doc.get("parsed_events") or [] if e.get("fact") in wanted), key=_fact_order)
    out.append(f"# events already tagged with these facts ({len(tagged)})")
    out += [f"#{e['fact']} {_span(e)} {e.get('label')}" for e in tagged]
    by_type: dict[str, list[str]] = {}
    for e in doc.get("candidate_entities") or []:
        by_type.setdefault(e.get("entity_type") or "?", []).append(e.get("label") or "?")
    n_ent = sum(len(v) for v in by_type.values())
    out.append(f"# entity labels already in the handoff ({n_ent}); reuse these exact strings, never re-add them")
    out += [f"{t}: " + "; ".join(labels) for t, labels in sorted(by_type.items())]
    out.append(f"# handoff now: {counts_line(doc)}")
    return out


# ── lint ────────────────────────────────────────────────────────────────────

def norm_label(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[\W_]+", "", text.casefold())


@dataclass
class LintReport:
    errors: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[tuple[str, str]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


def lint(doc: dict, *, era: str | None = None, facts: int | None = None,
         fact_numbers: Iterable[int] | None = None, scope: SliceScope | None = None,
         fact_map: dict[int, str] | None = None) -> LintReport:
    """Lint the whole handoff, or (scope) only what one fact slice owns: its items'
    problems, summaries, orphans, near-duplicates and mentions, plus slice density
    (relations per fact / per new entity) instead of the global ratios."""
    rep = LintReport()
    ctx = Ctx.from_doc(doc, era, fact_map)
    events = doc.get("parsed_events") or []
    entities = doc.get("candidate_entities") or []
    relations = doc.get("candidate_relations") or []
    summaries = doc.get("summaries") or {}
    numbers = set(fact_numbers) if fact_numbers is not None else None

    def add(sev: str, code: str, msg: str) -> None:
        (rep.errors if sev == "E" else rep.warnings).append((code, msg))

    def mine(part: str, item: Any) -> bool:
        return scope is None or (isinstance(item, dict) and scope.owns(part, item))

    for part, items in (("events", events), ("entities", entities), ("relations", relations)):
        seen: dict[Any, int] = {}
        owned: set[Any] = set()
        for i, item in enumerate(items):
            if isinstance(item, dict):
                key = item_key(part, item)
                seen[key] = seen.get(key, 0) + 1
                if mine(part, item):
                    owned.add(key)
            if not mine(part, item):
                continue
            _, probs = check_item(part, item, ctx)
            label = display(part, item) if isinstance(item, dict) else f"#{i}"
            for sev, code, msg in probs:
                add(sev, code, f"{SINGULAR[part]} {label!r}: {msg}")
        for key, n in seen.items():
            if n > 1 and (scope is None or key in owned):
                if part == "relations":
                    add("W", "duplicate", f"relation {rel_key_str(key)!r} x{n} (importer keeps only the first)")
                else:
                    add("E", "duplicate", f"{SINGULAR[part]} label {key!r} appears {n} times")

    entity_labels = [e.get("label") for e in entities if isinstance(e, dict)]
    if doc.get("summaries_precomputed"):
        for label in entity_labels:
            if scope is not None and label not in scope.entities:
                continue
            fields = summaries.get(label) or {}
            if not (fields.get("summary") or "").strip() or not (fields.get("significance") or "").strip():
                add("E", "summary-missing", f"entity {label!r}: missing summary/significance")
    if scope is None:
        for label in summaries:
            if label not in ctx.entities:
                add("W", "summary-orphan", f"summary {label!r} has no entity")

    ev_fact = {e.get("label"): e.get("fact") for e in events if isinstance(e, dict) and e.get("fact") is not None}
    used: set[str] = set()
    for r in relations:
        if isinstance(r, dict):
            used.update((r.get("source_label"), r.get("target_label")))
    orphans = [e for e in entities if isinstance(e, dict) and e.get("label") not in used and mine("entities", e)]
    for e in orphans:
        n = ev_fact.get(e.get("source_event"))
        add("W", "orphan", f"entity {e.get('label')!r} [{e.get('entity_type')}] has no relations"
            + (f" (fact {n})" if n else ""))

    by_norm: dict[str, list[str]] = {}
    for label in entity_labels:
        by_norm.setdefault(norm_label(label), []).append(label)
    for labels in by_norm.values():
        distinct = list(dict.fromkeys(labels))
        if len(distinct) > 1 and (scope is None or scope.entities & set(distinct)):
            add("W", "near-duplicate", " ~ ".join(repr(x) for x in distinct))
    for e in entities:
        if not isinstance(e, dict):
            continue
        for alias in e.get("aliases") or []:
            for other in by_norm.get(norm_label(alias), []):
                if other != e.get("label") and (scope is None or {other, e.get("label")} & scope.entities):
                    add("W", "near-duplicate", f"{e.get('label')!r} alias {alias!r} matches entity {other!r}")

    known = set(entity_labels)
    for ev in events:
        if not isinstance(ev, dict) or not mine("events", ev):
            continue
        missing = [m for m in ev.get("mentioned_entities") or [] if m not in known]
        if missing:
            add("W", "mention-missing", f"event {ev.get('label')!r} mentions {', '.join(map(repr, missing))}, "
                "which is not an entity label (add the entity or fix the spelling)")

    tagged = [e for e in events if isinstance(e, dict) and e.get("fact") is not None]
    if numbers is not None:
        for e in tagged:
            if e["fact"] not in numbers and mine("events", e):
                add("W", "fact-range", f"event {e.get('label')!r}: fact {e['fact']} is not a numbered transcript fact")
    if scope is None and tagged:
        untagged = [e.get("label") for e in events if isinstance(e, dict) and e.get("fact") is None]
        if untagged:
            add("W", "fact-missing", f"{len(untagged)} event(s) have no fact number: "
                + ", ".join(repr(x) for x in untagged[:10]) + (" ..." if len(untagged) > 10 else ""))
    expected = scope.facts if scope is not None else (sorted(numbers) if numbers and tagged else [])
    covered = {e.get("fact") for e in tagged}
    uncovered = [n for n in expected if (numbers is None or n in numbers) and n not in covered]
    if uncovered:
        add("W", "fact-uncovered", f"facts with no event: {fmt_facts(uncovered)}")

    if scope is not None:
        slice_facts = [n for n in scope.facts if numbers is None or n in numbers]
        n_rel = sum(1 for r in relations if mine("relations", r))
        n_new = len(scope.entities)
        per_fact = n_rel / len(slice_facts) if slice_facts else 0.0
        per_new = n_rel / n_new if n_new else None
        rep.stats = {"slice": fmt_facts(scope.facts), "facts": len(slice_facts), "events": len(scope.events),
                     "new_entities": n_new, "relations": n_rel, "rel/fact": round(per_fact, 2),
                     "rel/new_ent": None if per_new is None else round(per_new, 2), "orphans": len(orphans)}
        if slice_facts and per_fact < SLICE_REL_PER_FACT:
            add("W", "slice-density", f"relations/fact {per_fact:.2f} < {SLICE_REL_PER_FACT} "
                "(count = relations whose source_event is one of this slice's events)")
        if per_new is not None and per_new < SLICE_REL_PER_NEW_ENTITY:
            add("W", "slice-density", f"relations/new entity {per_new:.2f} < {SLICE_REL_PER_NEW_ENTITY}")
        return rep

    n_ev, n_en, n_rel = len(events), len(entities), len(relations)
    density = n_rel / n_en if n_en else 0.0
    per_event = n_en / n_ev if n_ev else 0.0
    rep.stats = {"facts": facts, "events": n_ev, "entities": n_en, "relations": n_rel,
                 "summaries": len(summaries), "r/e": round(density, 2),
                 "ent/ev": round(per_event, 2), "orphans": len(orphans)}
    if n_en and density < MIN_DENSITY:
        add("W", "density", f"relations/entities {density:.2f} < {MIN_DENSITY}")
    if n_ev and per_event < MIN_ENTITIES_PER_EVENT:
        add("W", "entities-per-event", f"entities/event {per_event:.2f} < {MIN_ENTITIES_PER_EVENT}")
    if facts is None:
        add("W", "transcript", "transcript missing (no fact count)")
    elif facts and n_ev < MIN_EVENTS_PER_FACT * facts:
        add("W", "event-coverage", f"{n_ev} events for {facts} numbered facts (< {MIN_EVENTS_PER_FACT:.0%})")
    if not doc.get("self_audit"):
        add("W", "self-audit", "no self_audit yet (run `handoff finalize`)")
    return rep


# ── show ────────────────────────────────────────────────────────────────────

def _span(item: dict) -> str:
    return f"{item.get('start_date') or ''}..{item.get('end_date') or ''}"


def show_lines(doc: dict, part: str, labels_only: bool = False) -> list[str]:
    if part == "summaries":
        out = []
        for label, fields in (doc.get("summaries") or {}).items():
            text = (fields or {}).get("summary") or ""
            out.append(label if labels_only else f"{label}: {text[:80]}")
        return out
    out = []
    for item in doc.get(PARTS[part]) or []:
        if labels_only:
            out.append(display(part, item))
        elif part == "events":
            tag = f"#{item['fact']} " if item.get("fact") is not None else ""
            out.append(f"{tag}{_span(item)} {item.get('label')}")
        elif part == "entities":
            out.append(f"{item.get('label')} [{item.get('entity_type')}] {_span(item)}")
        else:
            start = f" ({item['start_date']})" if item.get("start_date") else ""
            out.append(f"{item.get('source_label')} -{item.get('relationship_type')}-> {item.get('target_label')}{start}")
    return out


def get_items(doc: dict, part: str, keys: Iterable[str]) -> tuple[list[str], list[str]]:
    found, missing = [], []
    for raw in keys:
        if part == "summaries":
            label = raw.strip()
            fields = (doc.get("summaries") or {}).get(label)
            if fields is None:
                missing.append(raw)
            else:
                found.append(_j({"label": label, **fields}))
            continue
        key = parse_rel_key(raw) if part == "relations" else raw.strip()
        hits = [it for it in doc.get(PARTS[part]) or [] if item_key(part, it) == key]
        if not hits:
            missing.append(raw)
        found += [_j(h) for h in hits]
    return found, missing
