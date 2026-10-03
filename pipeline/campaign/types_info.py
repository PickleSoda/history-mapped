"""Allowed entity/relation types from code, with direction hints from the
relationship reference (docs/entity-model/relationships.md)."""
from __future__ import annotations

import re
from pathlib import Path

from pipeline.campaign.paths import REPO_ROOT

RELATIONSHIPS_DOC = REPO_ROOT / "docs" / "entity-model" / "relationships.md"
_ROW = re.compile(r"^\|\s*`([a-z_]+)`\s*\|(.+)\|\s*$")
_EXAMPLE = re.compile(r"^\*(.+?)\*\s*\*\*\[[a-z_]+\]\*\*\s*\*(.+?)\*")


def entity_types_by_group() -> dict[str, list[str]]:
    from pipeline.agent.graph.nodes.commit_writer import ENTITY_TYPE_TO_GROUP
    from pipeline.agent.schemas.entities import _CANONICAL_ENTITY_TYPES

    groups: dict[str, list[str]] = {}
    for t in sorted(_CANONICAL_ENTITY_TYPES):
        groups.setdefault(ENTITY_TYPE_TO_GROUP.get(t, "OTHER"), []).append(t)
    order = ["POLITY", "PLACE", "EVENT", "ECONOMY", "CULTURE", "OTHER"]
    return {g: groups[g] for g in order if g in groups}


def relation_types() -> list[str]:
    from pipeline.agent.graph.nodes.validate import ALLOWED_RELATION_TYPES

    return sorted(ALLOWED_RELATION_TYPES)


def relation_hints(doc: Path = RELATIONSHIPS_DOC) -> dict[str, str]:
    """`type -> "Source types → Target types"` (or an example pair when the doc
    row has no source/target columns). Types absent from the doc get no hint."""
    try:
        text = doc.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    hints: dict[str, str] = {}
    for line in text.splitlines():
        m = _ROW.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        if len(cells) >= 4:
            hints[m.group(1)] = f"{cells[1]} → {cells[2]}"
        elif cells:
            ex = _EXAMPLE.match(cells[-1])
            if ex:
                hints[m.group(1)] = f"e.g. {ex.group(1)} → {ex.group(2)}"
    return hints


def types_lines(with_hints: bool = False) -> list[str]:
    out = [f"entity {group}: {' '.join(types)}" for group, types in entity_types_by_group().items()]
    rels = relation_types()
    out.append(f"relations ({len(rels)}): {' '.join(rels)}")
    if with_hints:
        hints = relation_hints()
        out.append("relation direction (source → target):")
        out += [f"  {t}: {hints[t]}" for t in rels if t in hints]
    return out
