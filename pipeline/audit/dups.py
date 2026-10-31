"""C4: duplicate rows, with a proposed survivor and the exact merge command.

Three detectors:
  (a) same_qid       — two or more rows carry one QID;
  (b) same_name      — same normalised name and type, compatible dates (or,
                       for places, points within 25 km), and no two different QIDs;
  (c) disambiguator  — 'Battle of Salamis' vs 'Battle of Salamis (480 BCE)':
                       the same name once a trailing '(…)' is dropped, where the
                       qualifier's year fits the other row and QIDs don't differ.

Merges are never applied by the audit; the command uses
``pipeline.merge_entities.merge(cur, survivor, loser)`` by id, because the
name-based CLI merges *every* row with that name.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any

from pipeline.agent.tools.disambiguation import _name_tokens
from pipeline.audit.dates import tolerance

_TRAILING_PAREN = re.compile(r"\s*\(([^()]*)\)\s*$")
_YEAR_IN = re.compile(r"(\d{1,4})\s*(BCE|BC|CE|AD)?", re.I)


def norm(name: str) -> str:
    return " ".join(_name_tokens(name))


def strip_qualifier(name: str) -> tuple[str, str | None]:
    m = _TRAILING_PAREN.search(name)
    if not m:
        return name, None
    return name[:m.start()].strip(), m.group(1).strip()


def qualifier_year(qualifier: str | None) -> int | None:
    if not qualifier:
        return None
    m = _YEAR_IN.search(qualifier)
    if not m:
        return None
    year = int(m.group(1))
    return -year if (m.group(2) or "").upper().startswith("B") else year


def km(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float | None:
    if not a or not b:
        return None
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(min(1.0, h)))


def date_fit(etype: str, a, b) -> str:
    """'match' | 'near' | 'conflict' | 'unknown' for two row spans.

    Sign-sensitive, unlike the namesake guard's temporal_gap: two rows dated
    -222 and 237 are different eras, not a mis-signed duplicate. Uses the C2
    tolerances (person 5, event 2, polity 25), stricter than the namesake guard
    (Constantine IV 652-685 is not Constantine V 720-775)."""
    tol = tolerance(etype)
    if tol is None or a is None or b is None:
        return "unknown"
    gap = max(0, max(a[0], b[0]) - min(a[1], b[1]))
    return "match" if gap == 0 else "near" if gap <= tol else "conflict"


def pair_ok(x, y) -> tuple[bool, str, str]:
    """(is a duplicate candidate, confidence, evidence) for two same-type rows."""
    if x.qid and y.qid and x.qid != y.qid:
        return False, "", "different QIDs"
    fit = date_fit(x.type, x.span, y.span)
    if fit == "conflict":
        return False, "", "different eras"
    dist = km(x.point, y.point)
    if dist is not None and dist > 300 and x.group == "PLACE":
        return False, "", f"{dist:.0f} km apart"
    ev = [f"dates {fit}"]
    if dist is not None:
        ev.append(f"{dist:.0f} km apart")
    if fit == "match" or (dist is not None and dist <= 25):
        conf = "high"
    elif fit == "near" or (dist is not None and dist <= 100):
        conf = "medium"
    else:
        conf = "low"
    return True, conf, ", ".join(ev)


def survivor_key(r) -> tuple:
    return (r.rels, bool(r.qid), r.has_geo, len(r.text), r.chron, bool(r.stories), _neg_time(r.created_at))


def _neg_time(ts: str) -> str:
    # older rows first among ties: invert the timestamp's digits
    return "".join(chr(0x7f - ord(c)) for c in ts)


def merge_command(survivor: str, loser: str) -> str:
    return ("scripts/capped.sh pipeline/.venv/bin/python3 -c \"import psycopg; "
            "from pipeline.merge_entities import merge, DSN; c=psycopg.connect(DSN); "
            f"merge(c.cursor(), '{survivor}', '{loser}'); c.commit()\"")


def _groups(pairs: list[tuple[str, str]]) -> list[set[str]]:
    parent: dict[str, str] = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in pairs:
        parent[find(a)] = find(b)
    out: dict[str, set[str]] = defaultdict(set)
    for a in parent:
        out[find(a)].add(a)
    return [g for g in out.values() if len(g) > 1]


def find_duplicates(rows: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[tuple[str, set[str], str, str]] = []  # (category, ids, confidence, evidence)
    seen_pairs: set[frozenset] = set()

    # (a) same QID
    by_qid: dict[str, list[str]] = defaultdict(list)
    for r in rows.values():
        if r.qid:
            by_qid[r.qid].append(r.id)
    for qid, ids in by_qid.items():
        if len(ids) > 1:
            found.append(("same_qid", set(ids), "high", f"all carry {qid}"))
            seen_pairs |= {frozenset((a, b)) for a in ids for b in ids if a != b}

    # (b) same normalised name + type
    by_name: dict[tuple[str, str], list] = defaultdict(list)
    for r in rows.values():
        key = norm(r.name)
        if key:
            by_name[(key, r.type)].append(r)
    for (key, _), group in by_name.items():
        if len(group) < 2:
            continue
        pairs, confs, evs = [], [], []
        for i, x in enumerate(group):
            for y in group[i + 1:]:
                if frozenset((x.id, y.id)) in seen_pairs:
                    continue
                ok, conf, ev = pair_ok(x, y)
                if ok:
                    pairs.append((x.id, y.id))
                    confs.append(conf)
                    evs.append(ev)
        for g in _groups(pairs):
            gc = [c for (a, b), c in zip(pairs, confs) if a in g]
            ge = sorted({e for (a, b), e in zip(pairs, evs) if a in g})
            conf = "high" if "high" in gc and all(c != "low" for c in gc) else ("medium" if "low" not in gc else "low")
            found.append(("same_name", g, conf, "; ".join(ge)))
            seen_pairs |= {frozenset((a, b)) for a in g for b in g if a != b}

    # (c) disambiguator variants
    by_base: dict[tuple[str, str], list] = defaultdict(list)
    for r in rows.values():
        base, qual = strip_qualifier(r.name)
        by_base[(norm(base), r.type)].append((r, qual))
    for (key, _), group in by_base.items():
        if len(group) < 2 or all(q is None for _, q in group):
            continue
        pairs, evs, confs = [], [], []
        for i, (x, qx) in enumerate(group):
            for y, qy in group[i + 1:]:
                if (qx is None) == (qy is None) or frozenset((x.id, y.id)) in seen_pairs:
                    continue  # only bare-name vs qualified-name pairs
                ok, conf, ev = pair_ok(x, y)
                if not ok:
                    continue
                qual, other = (qx, y) if qx is not None else (qy, x)
                year = qualifier_year(qual)
                tol = tolerance(x.type) or 25
                if year is None:
                    # a word qualifier usually names a different thing ('Rome (New York)',
                    # 'Kingdom of Poland (Congress Poland)'): require overlapping dates or
                    # points within 25 km
                    dist = km(x.point, y.point)
                    if date_fit(x.type, x.span, y.span) != "match" and not (dist is not None and dist <= 25):
                        continue
                if year is not None:
                    if other.span is None:
                        conf = "low"
                    elif not (other.span[0] - tol <= year <= other.span[1] + tol):
                        continue
                    else:
                        ev += f"; '({qual})' fits the bare row's dates"
                pairs.append((x.id, y.id))
                evs.append(ev)
                confs.append(conf)
        for g in _groups(pairs):
            gc = [c for (a, b), c in zip(pairs, confs) if a in g]
            conf = "high" if gc and all(c == "high" for c in gc) else "medium" if "low" not in gc else "low"
            found.append(("disambiguator", g, conf, "; ".join(sorted({e for (a, b), e in zip(pairs, evs) if a in g}))))

    out = []
    for n, (cat, ids, conf, ev) in enumerate(found, 1):
        members = sorted((rows[i] for i in ids), key=survivor_key, reverse=True)
        surv = members[0]
        qids = sorted({m.qid for m in members if m.qid})
        for loser in members[1:]:
            if cat != "same_qid" and not pair_ok(surv, loser)[0]:
                continue  # chained into the group through a third row; not a duplicate of the survivor
            moves = [f"{loser.rels} relationship ends (colliding ones dropped)", f"{loser.chron} chronicle links"]
            lost = []
            if loser.aliases or loser.name != surv.name:
                lost.append("its name/aliases (add as aliases on the survivor)")
            if loser.has_geo:
                lost.append("its geometry")
            if loser.qid and not surv.qid:
                lost.append(f"QID {loser.qid} (then set it on the survivor)")
            if loser.stories:
                lost.append(f"MAP STORY {','.join(loser.stories)} (CASCADE: re-point map_stories.entity_id first)")
            cmd = merge_command(surv.id, loser.id)
            if loser.qid and not surv.qid:
                cmd += f" && docker compose -f docker/docker-compose.yml exec -T db psql -U history-mapped history-mapped -c \"UPDATE entities SET wikidata_id='{loser.qid}' WHERE entity_id='{surv.id}' AND wikidata_id IS NULL\""
            out.append({
                "group": n, "category": cat, "confidence": conf, "evidence": ev,
                "survivor_id": surv.id, "survivor_name": surv.name, "survivor_qid": surv.qid,
                "survivor_rels": surv.rels, "loser_id": loser.id, "loser_name": loser.name,
                "loser_qid": loser.qid, "loser_rels": loser.rels, "entity_type": surv.type,
                "survivor_span": surv.span, "loser_span": loser.span, "qids_in_group": qids,
                "moves": "; ".join(moves), "lost_on_delete": "; ".join(lost), "merge_command": cmd,
            })
    return out
