"""C8: battle-map identity check (report only — story files are never edited).

For every story in api/resources/map-stories/*.json, each QID in ``entity``,
``sides[].polity``, ``sides[].commanders[]`` and ``units[]`` is checked:

* against Wikidata under C2's rules (name, class, and era: a commander alive
  at the battle, a polity existing then, the battle in its year);
* against the DB row the API resolves it to (``SyncMapStoryFileAction::byQid``:
  highest impact_score, then entity_id): same name family, expected type,
  dated in the battle's era;
* commanders named without a QID get a proposed QID when exactly one Wikidata
  human with that name was alive at the battle.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.agent.tools.disambiguation import candidate_name_ok
from pipeline.audit import classes as C
from pipeline.audit.common import STORIES_DIR, STORY_SOURCES
from pipeline.audit.dates import PRECISION_SLACK, wd_bounds
from pipeline.audit.qid import wd_names

# 'subject' = the entity of a non-battle story (an epidemic, a trade league):
# only its name, state and DB row are checked
ROLE_TYPE = {"entity": "event_battle", "subject": None, "polity": "political_entity", "commander": "person",
             "unit": "military_unit"}
ROW_TYPES = {"event_battle": {"event_battle", "event_war", "event_rebellion"},
             "political_entity": {"political_entity", "dynasty", "diplomatic_relationship", "military_unit"},
             "person": {"person"}, "military_unit": {"military_unit"}}
ERA_TOL = {"event_battle": 2, "political_entity": 25, "person": 0, "military_unit": 25}


def story_refs(doc: dict[str, Any]) -> list[dict[str, Any]]:
    refs = []
    if isinstance(doc.get("entity"), dict):  # chronicle stories carry no entity QID
        refs.append({"where": "entity", "name": doc["entity"].get("name"), "qid": doc["entity"].get("wikidata"),
                     "role": "entity" if doc.get("kind", "battle") == "battle" else "subject"})
    for i, side in enumerate(doc.get("sides", [])):
        pol = side.get("polity")
        if isinstance(pol, dict):
            refs.append({"where": f"sides[{i}].polity", "name": pol.get("name"), "qid": pol.get("wikidata"),
                         "role": "polity", "side": side.get("id")})
        for j, cmd in enumerate(side.get("commanders", []) or []):
            refs.append({"where": f"sides[{i}].commanders[{j}]", "name": cmd.get("name"),
                         "qid": cmd.get("wikidata"), "role": "commander", "side": side.get("id")})
    for k, unit in enumerate(doc.get("units", []) or []):
        if unit.get("wikidata"):
            refs.append({"where": f"units[{k}] ({unit.get('id')})", "name": unit.get("label") or unit.get("id"),
                         "qid": unit.get("wikidata"),
                         "role": "commander" if unit.get("kind") == "commander" else "unit"})
    return refs


def story_span(doc: dict[str, Any]) -> tuple[int, int]:
    """The years a story covers: its period (a plague's 1346-1353, a league's
    1241-1598) or, for a battle, its one year."""
    period = doc.get("period") or {}
    start = (period.get("start") or {}).get("year", doc.get("year"))
    end = (period.get("end") or {}).get("year", start)
    return start, end


def era_ok(etype: str, rec: dict[str, Any], span: tuple[int, int]) -> tuple[bool | None, str]:
    start, end = wd_bounds(etype, rec.get("dates") or {})
    if not start and not end:
        return None, "no Wikidata dates"
    tol = ERA_TOL[etype]
    lo = start[0] - PRECISION_SLACK.get(start[1], 0) - tol if start else None
    hi = end[0] + PRECISION_SLACK.get(end[1], 0) + tol if end else None
    if etype == "event_battle":
        lo = lo if lo is not None else hi
        hi = hi if hi is not None else lo
    if etype == "person" and lo is not None and hi is None:
        hi = lo + 100 + tol
    ok = (lo is None or lo <= span[1]) and (hi is None or span[0] <= hi)
    span = f"{start[0] if start else '?'}..{end[0] if end else '?'}"
    return ok, f"Wikidata {span}"


def row_era_ok(row, etype: str, span: tuple[int, int]) -> bool | None:
    if row.span is None:
        return None
    tol = {"person": 5, "event_battle": 2}.get(etype, 25)
    return row.span[0] - tol <= span[1] and span[0] <= row.span[1] + tol


def check_story(path: Path, client, closure_fn, rows_by_qid: dict[str, list]) -> list[dict[str, Any]]:
    doc = json.loads(path.read_text())
    year = doc.get("year")
    span = story_span(doc)
    when = str(year) if span[0] == span[1] else f"{span[0]}-{span[1]}"
    refs = story_refs(doc)
    client.get_entities([r["qid"] for r in refs if r.get("qid")])
    p31 = [c for r in refs if r.get("qid") for c in (client.resolved(r["qid"])[1] or {}).get("p31", [])]
    closure = closure_fn(p31)
    out = []
    for ref in refs:
        etype = ROLE_TYPE[ref["role"]]
        res = {"story": path.name, "source": str((STORY_SOURCES / (path.stem.replace("-", "_") + ".py")).relative_to(
            STORY_SOURCES.parents[2])), "where": ref["where"], "name": ref["name"], "qid": ref.get("qid") or "",
            "role": ref["role"], "year": year, "problems": [], "proposed_qid": "", "evidence": "", "db_row": ""}
        if not ref.get("qid"):
            if ref["role"] == "commander":
                prop = propose_person(ref["name"], span, client, closure_fn)
                res.update(prop)
            out.append(res)
            continue
        final, rec = client.resolved(ref["qid"])
        if final != ref["qid"]:
            res["problems"].append(f"redirect to {final}")
            res["proposed_qid"] = final
        if not rec or rec.get("status") != "ok":
            res["problems"].append("QID deleted on Wikidata")
            out.append(res)
            continue
        res["wd_label"] = rec.get("label", "")
        res["wd_description"] = rec.get("description", "")
        ok, why = candidate_name_ok([ref["name"]], wd_names(rec))
        if not ok:
            res["problems"].append(f"name '{ref['name']}' vs Wikidata '{rec.get('label')}' ({why})")
        if etype is None:
            if C.junk_label(rec.get("p31", [])):
                res["problems"].append(f"QID is a {C.junk_label(rec.get('p31', []))}")
            cands = rows_by_qid.get(final) or rows_by_qid.get(ref["qid"]) or []
            res["db_row"] = (f"{cands[0].id} {cands[0].name!r} {cands[0].type} {cands[0].span}" if cands
                             else "none (not in the atlas)")
            out.append(res)
            continue
        klass = C.classify(etype if etype != "military_unit" else "military_unit", rec.get("p31", []), closure)
        if klass == "contradiction" or (klass == "unmatched" and ref["role"] != "unit"):
            res["problems"].append(f"class {klass} for a {etype} ({C.kind_label(C.kinds_of(rec.get('p31', []), closure))})")
        era, era_note = era_ok(etype, rec, span)
        res["wd_era"] = era_note
        if era is False:
            res["problems"].append(f"not of the story's era: {era_note}, story {when}")
        # the DB row the API resolves the QID to
        cands = rows_by_qid.get(final) or rows_by_qid.get(ref["qid"]) or []
        if not cands:
            res["db_row"] = "none (not in the atlas)"
        else:
            row = cands[0]
            res["db_row"] = f"{row.id} {row.name!r} {row.type} {row.span}"
            if not candidate_name_ok(row.names, [ref["name"], *wd_names(rec)])[0]:
                res["problems"].append(f"DB row named {row.name!r}")
            if row.type not in ROW_TYPES[etype]:
                res["problems"].append(f"DB row typed {row.type}")
            if row_era_ok(row, etype, span) is False:
                res["problems"].append(f"DB row dated {row.span}, story {when}")
            if len(cands) > 1:
                res["problems"].append(f"{len(cands)} DB rows share the QID")
        if any(not p.startswith("DB ") and not p.startswith("redirect") for p in res["problems"]):
            res.update({k: v for k, v in propose_for_ref(ref, etype, span, client, closure_fn).items() if v})
        out.append(res)
    return out


def _person_ok(rec: dict[str, Any], name: str, span: tuple[int, int], closure) -> dict[str, bool]:
    era, _ = era_ok("person", rec, span)
    start, _end = wd_bounds("person", rec.get("dates") or {})
    return {"name": candidate_name_ok([name], wd_names(rec))[0],
            "class": "Q5" in (rec.get("p31") or []),
            "era": bool(era) and (start is None or span[0] - start[0] <= 90),
            "enwiki": bool(rec.get("enwiki"))}


def propose_person(name: str, span: tuple[int, int], client, closure_fn) -> dict[str, Any]:
    year = span[0] if span[0] == span[1] else f"{span[0]}-{span[1]}"
    hits = client.search(name, limit=10)
    client.get_entities([h["qid"] for h in hits])
    scored = []
    for h in hits:
        _, rec = client.resolved(h["qid"])
        if rec and rec.get("status") == "ok":
            checks = _person_ok(rec, name, span, None)
            scored.append((h["qid"], rec, checks))
    passing = [s for s in scored if all(s[2].values())]
    near = [s for s in scored if s[2]["name"] and s[2]["class"] and s[2]["era"]]
    if len(passing) == 1 and len(near) == 1:
        q, rec, _ = passing[0]
        return {"proposed_qid": q, "evidence": f"only Wikidata human named like '{name}' alive in {year}: "
                                               f"{rec.get('label')} — {rec.get('description')}",
                "problems": ["no QID; one clear match"]}
    if near:
        return {"evidence": "several candidates: " + "; ".join(f"{q} {r.get('label')}" for q, r, _ in near[:4]),
                "problems": ["no QID; ambiguous"]}
    return {"problems": []}


def propose_for_ref(ref, etype: str, span: tuple[int, int], client, closure_fn) -> dict[str, Any]:
    year = span[0] if span[0] == span[1] else f"{span[0]}-{span[1]}"
    if etype == "person":
        prop = propose_person(ref["name"], span, client, closure_fn)
        prop.pop("problems", None)
        return prop
    hits = [h for h in client.search(ref["name"], limit=10) if h["qid"] != ref["qid"]]
    client.get_entities([h["qid"] for h in hits])
    recs = [(h["qid"], client.resolved(h["qid"])[1]) for h in hits]
    recs = [(q, r) for q, r in recs if r and r.get("status") == "ok"]
    closure = closure_fn([c for _, r in recs for c in r.get("p31", [])])
    good = []
    for q, r in recs:
        if not candidate_name_ok([ref["name"]], wd_names(r))[0]:
            continue
        if C.classify(etype, r.get("p31", []), closure) != "ok":
            continue
        if era_ok(etype, r, span)[0] is not True:
            continue
        good.append((q, r))
    if len(good) == 1:
        q, r = good[0]
        return {"proposed_qid": q, "evidence": f"only {etype} candidate named like '{ref['name']}' of {year}: "
                                               f"{r.get('label')} — {r.get('description')}"}
    if good:
        return {"evidence": "candidates: " + "; ".join(f"{q} {r.get('label')} ({r.get('description')})" for q, r in good[:4])}
    return {}


def check_all(client, closure_fn, rows: dict[str, Any]) -> list[dict[str, Any]]:
    rows_by_qid: dict[str, list] = {}
    for r in sorted(rows.values(), key=lambda r: (-(r.impact if r.impact is not None else -10**9), r.id)):
        if r.qid:
            rows_by_qid.setdefault(r.qid, []).append(r)
    out = []
    for path in sorted(STORIES_DIR.glob("*.json")):
        out.extend(check_story(path, client, closure_fn, rows_by_qid))
    return out
