import json

import pytest
from click.testing import CliRunner

from pipeline.campaign.__main__ import cli

SLUG = "e08__caucasus__georgian-golden-age"
RUN_ID = f"campaign_{SLUG}"

TRANSCRIPT = """Georgia's Golden Age (1089-1213 CE)

1. David IV becomes king of Georgia in 1089 CE.
2. David IV defeats the Seljuks at the Battle of Didgori in 1121 CE.
3) Tamar of Georgia rules the kingdom from 1184 to 1213 CE.
Not a numbered line.
"""

EVENTS = [
    {"label": "Accession of David IV", "description": "David IV becomes king.", "start_date": "1089",
     "mentioned_entities": ["David IV of Georgia", "Kingdom of Georgia"]},
    {"label": "Battle of Didgori", "description": "David IV defeats the Seljuks.", "start_date": 1121,
     "mentioned_entities": ["David IV of Georgia", "Seljuk Empire"]},
    {"label": "Reign of Tamar", "description": "Tamar rules Georgia.", "start_date": "1184", "end_date": "1213",
     "mentioned_entities": ["Tamar of Georgia"]},
]
ENTITIES = [
    {"label": "David IV of Georgia", "entity_type": "person", "start_date": "1073", "end_date": "1125",
     "source_event": "Accession of David IV", "aliases": ["David the Builder"]},
    {"label": "Kingdom of Georgia", "entity_type": "political_entity", "start_date": "1008",
     "source_event": "Accession of David IV"},
    {"label": "Seljuk Empire", "entity_type": "political_entity", "start_date": "1037", "end_date": "1194",
     "source_event": "Battle of Didgori"},
    {"label": "Battle of Didgori", "entity_type": "event_battle", "start_date": "1121", "end_date": "1121",
     "source_event": "Battle of Didgori"},
    {"label": "Tamar of Georgia", "entity_type": "person", "start_date": "1160", "end_date": "1213",
     "source_event": "Reign of Tamar"},
]
RELATIONS = [
    {"source_label": "David IV of Georgia", "relationship_type": "rules", "target_label": "Kingdom of Georgia",
     "start_date": "1089", "end_date": "1125", "source_event": "Accession of David IV",
     "description": "David IV ruled Georgia."},
    {"source_label": "Kingdom of Georgia", "relationship_type": "victorious_at", "target_label": "Battle of Didgori",
     "start_date": "1121", "source_event": "Battle of Didgori", "description": "Georgian victory."},
    {"source_label": "Seljuk Empire", "relationship_type": "defeated_at", "target_label": "Battle of Didgori",
     "start_date": "1121", "source_event": "Battle of Didgori", "description": "Seljuk defeat."},
    {"source_label": "Tamar of Georgia", "relationship_type": "rules", "target_label": "Kingdom of Georgia",
     "start_date": "1184", "end_date": "1213", "source_event": "Reign of Tamar", "description": "Tamar ruled."},
    {"source_label": "Seljuk Empire", "relationship_type": "at_war_with", "target_label": "Kingdom of Georgia",
     "start_date": "1121", "source_event": "Battle of Didgori", "description": "War with Georgia."},
    {"source_label": "David IV of Georgia", "relationship_type": "commanded", "target_label": "Battle of Didgori",
     "start_date": "1121", "source_event": "Battle of Didgori", "description": "Led the army."},
    {"source_label": "Tamar of Georgia", "relationship_type": "resided_in", "target_label": "Kingdom of Georgia",
     "start_date": "1184", "source_event": "Reign of Tamar", "description": "Lived in her kingdom."},
]
SUMMARIES = {
    label: {"summary": f"{label} summary sentence.", "significance": f"{label} mattered."}
    for label in (e["label"] for e in ENTITIES)
}


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMPAIGN_ROOT", str(tmp_path))
    monkeypatch.setenv("AGENT_OUTPUT_DIR", str(tmp_path / "agent_runs"))
    monkeypatch.chdir(tmp_path)
    tdir = tmp_path / "output" / "transcripts" / "campaign"
    tdir.mkdir(parents=True)
    (tdir / f"{SLUG}.txt").write_text(TRANSCRIPT, encoding="utf-8")
    return tmp_path


@pytest.fixture
def invoke(root):
    runner = CliRunner()

    def _invoke(*args, input=None):
        return runner.invoke(cli, [str(a) for a in args], input=input, catch_exceptions=False)

    return _invoke


@pytest.fixture
def built(invoke, root):
    """A complete, valid handoff authored through the CLI."""
    assert invoke("handoff", "init", SLUG, "--title", "Golden Age").exit_code == 0
    for part, payload in (("events", EVENTS), ("entities", ENTITIES), ("relations", RELATIONS),
                          ("summaries", SUMMARIES)):
        res = invoke("handoff", "add", SLUG, part, "-", input=json.dumps(payload))
        assert res.exit_code == 0, res.output
    return root / "output" / "campaign" / "extractions" / RUN_ID / "candidates.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))
