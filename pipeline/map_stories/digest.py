"""A story's text without its coordinates, and a check of its Wikidata links.

    python -m pipeline.map_stories digest api/resources/map-stories/battle-of-x.json          # all prose, ~1/5 of the JSON
    python -m pipeline.map_stories digest <json> --step hougoumont                             # one step
    python -m pipeline.map_stories digest <json> --links                                       # every Q-id vs its Wikidata label/class

For reviewers: fact-check the prose against `research --section`, and the
links against Wikidata, without reading the coordinate-heavy JSON.
"""

from __future__ import annotations

import re

#: Wikidata classes that never fit a role (by label substring).
BAD_FOR = {
    "commander": ("village", "parish", "city", "town", "river", "family name", "given name", "disambiguation", "battle", "country"),
    "polity": ("human", "village", "civil parish", "family name", "given name", "disambiguation", "battle", "river"),
    "entity": ("human", "village", "disambiguation", "family name", "given name"),
    "unit": ("village", "parish", "family name", "given name", "disambiguation"),
    "step": ("family name", "given name", "disambiguation", "album", "film", "song"),
    "feature": ("family name", "given name", "disambiguation", "album", "film", "song"),
}


def links(doc: dict) -> list[tuple[str, str, str]]:
    """(role, name in the story, Q-id) for every linked thing."""
    out = []
    ent = doc.get("entity") or {}
    if ent.get("wikidata"):
        out.append(("entity", ent.get("name", ""), ent["wikidata"]))
    for s in doc.get("sides") or []:
        pol = s.get("polity") or {}
        if pol.get("wikidata"):
            out.append(("polity", pol.get("name", ""), pol["wikidata"]))
        for c in pol.get("contingents") or s.get("contingents") or []:
            if isinstance(c, dict) and c.get("wikidata"):
                out.append(("polity", c.get("name", ""), c["wikidata"]))
        for c in s.get("commanders") or []:
            if c.get("wikidata"):
                out.append(("commander", c.get("name", ""), c["wikidata"]))
    for u in doc.get("units") or []:
        if u.get("wikidata"):
            out.append(("commander" if u.get("kind") == "commander" else "unit", u.get("label", ""), u["wikidata"]))
    # schema 3: features' entities, step entities and area_from_entity refs
    for f in doc.get("features") or doc.get("terrain") or []:
        ref = f.get("entity") if isinstance(f, dict) else None
        if isinstance(ref, dict) and ref.get("wikidata"):
            out.append(("feature", ref.get("name", ""), ref["wikidata"]))
    for st in doc.get("steps") or []:
        for e in st.get("entities") or []:
            if isinstance(e, dict) and e.get("wikidata"):
                out.append(("step", e.get("name", ""), e["wikidata"]))
        for fid, state in (st.get("features") or st.get("terrain_state") or {}).items():
            ref = state.get("area_from_entity") if isinstance(state, dict) else None
            if isinstance(ref, dict) and ref.get("wikidata"):
                out.append(("feature", ref.get("name", fid), ref["wikidata"]))
    seen, uniq = set(), []
    for row in out:
        if (row[1], row[2]) not in seen:
            seen.add((row[1], row[2]))
            uniq.append(row)
    return uniq


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-zÀ-ɏ]{3,}", s.casefold())} - {"the", "and", "battle", "army", "von", "der", "les"}


def _overlap(a: set[str], b: set[str]) -> bool:
    """Shared word, or a shared 5-letter stem (Macedon / Macedonia)."""
    return bool(a & b) or any(len(x) >= 5 and len(y) >= 5 and x[:5] == y[:5] for x in a for y in b)


def link_lines(doc: dict) -> list[str]:
    from pipeline.map_stories.net import wd_entities, wd_labels

    rows = links(doc)
    wd = wd_entities([q for _, _, q in rows])
    classes = wd_labels([c for r in wd.values() for c in (r.get("p31") or [])[:3]])
    out, bad = [], 0
    for role, name, qid in rows:
        r = wd.get(qid) or {}
        if r.get("missing") or not r:
            out.append(f"BAD   {role:9} {name[:30]:30} {qid}: no such item")
            bad += 1
            continue
        label = r.get("label") or "?"
        kinds = [classes.get(c, c) for c in (r.get("p31") or [])[:3]]
        flags = []
        if not _overlap(_words(name), _words(label + " " + (r.get("description") or ""))):
            flags.append("name≠label")
        if any(b in k.casefold() for k in kinds for b in BAD_FOR.get(role, ())):
            flags.append("class")
        if role == "commander" and "human" not in kinds:
            flags.append("not human")
        bad += bool(flags)
        out.append(f"{'CHECK' if flags else 'ok   '} {role:9} {name[:30]:30} {qid:10} → {label[:34]} ({', '.join(kinds)[:40]}){' ← ' + ', '.join(flags) if flags else ''}")
    out.insert(0, f"{len(rows)} links, {bad} to check")
    return out


def prose(doc: dict, step: str | None = None) -> list[str]:
    lines: list[str] = []
    if step is None:
        lines += [f"{doc.get('title')} — {doc.get('date_label')} ({doc.get('kind')}, schema {doc.get('schema')}, {len(doc.get('steps') or [])} steps)",
                  f"INTRO: {doc.get('intro', '')}", f"OUTCOME: {doc.get('outcome', '')}", f"UNCERTAINTY: {doc.get('uncertainty', '')}"]
        for s in doc.get("sides") or []:
            cmd = "; ".join(f"{c.get('name')}{' [' + c['wikidata'] + ']' if c.get('wikidata') else ''}" for c in s.get("commanders") or [])
            pol = s.get("polity") or {}
            lines.append(f"SIDE {s.get('id')}: {s.get('name')} | polity {pol.get('name')} [{pol.get('wikidata', '-')}] | {cmd} | strength {s.get('strength', '?')} | losses {s.get('losses', '?')}")
        lines.append("UNITS: " + "; ".join(f"{u.get('id')} ({u.get('side')}, {u.get('kind')}, {u.get('strength', '?')}): {u.get('label')}" for u in doc.get("units") or []))
        lines.append("SOURCES: " + "; ".join(s.get("title", "") for s in doc.get("sources") or []))
    for st in doc.get("steps") or []:
        if step is not None and st.get("id") != step:
            continue
        notes = " | ".join(n.get("text", "") for n in st.get("notes") or [])
        ents = "; ".join(f"{e.get('name')}{' (' + e['role'] + ')' if e.get('role') else ''}" for e in st.get("entities") or [] if isinstance(e, dict))
        head = f"[{st.get('id')}] {st.get('title')} ({st.get('time', '')}){' · entry ' + str(st['entry']) if 'entry' in st else ''}"
        lines.append(f"\n{head}\n{st.get('narrative', '')}" + (f"\n  notes: {notes}" if notes else "") + (f"\n  entities: {ents}" if ents else ""))
    return lines
