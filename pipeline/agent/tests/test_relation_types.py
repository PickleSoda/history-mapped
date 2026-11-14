"""The agent's relation types: what the extractor offers, the validator accepts."""
from __future__ import annotations

import re
from pathlib import Path

from pipeline.agent.graph.nodes import extract_candidates
from pipeline.agent.graph.nodes.validate import ALLOWED_RELATION_TYPES

ENUM = Path(__file__).resolve().parents[3] / "api/app/Enums/RelationshipType.php"


def _prompt_relation_types() -> set[str]:
    source = Path(extract_candidates.__file__).read_text(encoding="utf-8")
    block = source[source.index("Allowed relation types"):source.index("CRITICAL RULES")]
    types: set[str] = set()
    for line in block.splitlines():
        if "—" in line:  # "Political — rules, governed_by, ..."
            types |= {t.strip() for t in line.split("—", 1)[1].split(",") if t.strip()}
    return types


def test_relation_types_match_the_prompt() -> None:
    prompt = _prompt_relation_types()
    assert {"allied_with", "trades_with", "caused", "resulted_from"} <= prompt
    assert prompt == ALLOWED_RELATION_TYPES


def test_relation_types_are_all_in_the_app_enum() -> None:
    enum = set(re.findall(r"case \w+ = '([a-z_]+)'", ENUM.read_text(encoding="utf-8")))
    assert ALLOWED_RELATION_TYPES <= enum
