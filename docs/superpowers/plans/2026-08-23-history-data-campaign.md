# History Data Campaign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable opencode-authored extraction handoffs to flow through the existing LangGraph pipeline's deterministic tail, then run a ~300-transcript data campaign covering 9000 BCE–2000 CE.

**Architecture:** Opencode sessions perform the graph's LLM half offline (parse → extract → critic recall → summaries) and write `candidates.json` handoff files. A new `--from-candidates` CLI hydrates `AgentRunState` from the handoff and invokes the compiled graph starting at `db_lookup`; every downstream node (Wikidata resolution, OHM geo, validation, diff, commit, chronicle, audit) runs unchanged. A validation gate CLI fails fast on malformed handoffs before any DB work.

**Tech Stack:** Python 3.12 (`pipeline/.venv`), LangGraph/LangChain, pydantic v2, Click; Laravel importers via Docker Compose artisan; bash driver.

**Spec:** `docs/superpowers/specs/2026-08-23-history-data-campaign-design.md`

**Repo rules that bind every task:**
- GitNexus: run impact analysis before editing any symbol (see `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md`; use MCP tools if available). Report blast radius in the task notes.
- TDD: failing test first for every behavior change.
- Python commands run via `pipeline/.venv/bin/python` from repo root (host has no system pip).
- Docker-dependent steps require `docker compose -f docker/docker-compose.yml up -d` first.
- No comments in code unless matching an adjacent existing comment style explaining *why*.

---

### Task 1: State keys + handoff loader

**Files:**
- Modify: `pipeline/agent/graph/state.py`
- Create: `pipeline/agent/handoff.py`
- Test: `pipeline/agent/tests/test_handoff.py`

- [ ] **Step 1: Impact analysis**

Run impact on `AgentRunState` (upstream). Expected blast radius: all nodes read state keys; adding two new optional keys is additive — note it in task output.

- [ ] **Step 2: Write the failing test**

```python
# pipeline/agent/tests/test_handoff.py
import json
from pathlib import Path

import pytest

from pipeline.agent.handoff import HandoffDocument, hydrate_state, load_handoff


def _sample_doc() -> dict:
    return {
        "run_id": "campaign_test",
        "source_transcript": "output/transcripts/campaign/sample.txt",
        "title": "Test Chronicle",
        "summaries_precomputed": True,
        "parsed_events": [
            {"label": "Battle of Didgori", "description": "David IV defeats Ilghazi.",
             "start_date": "1121", "end_date": None,
             "mentioned_entities": ["David IV"], "date_uncertain": False}
        ],
        "candidate_entities": [
            {"label": "David IV of Georgia", "entity_type": "person",
             "start_date": "1073", "end_date": "1125", "aliases": ["David IV"]},
            {"label": "Kingdom of Georgia", "entity_type": "political_entity"},
            {"label": "Battle of Didgori", "entity_type": "event_battle",
             "start_date": "1121", "end_date": "1121"},
        ],
        "candidate_relations": [
            {"source_label": "David IV of Georgia", "target_label": "Battle of Didgori",
             "relationship_type": "participated_in", "start_date": "1121", "end_date": "1121",
             "description": "David IV commanded the Georgian forces at Didgori."},
            {"source_label": "David IV of Georgia", "target_label": "Kingdom of Georgia",
             "relationship_type": "rules", "start_date": "1089", "end_date": "1125",
             "description": "Ruled the Kingdom of Georgia from 1089 to 1125."}
        ],
        "summaries": {
            "David IV of Georgia": {"summary": "He ruled Georgia. He won at Didgori. His reign began the Golden Age.",
                                     "significance": "Broke Seljuk dominance."},
            "Kingdom of Georgia": {"summary": "The kingdom rose in the Caucasus. It flourished under David IV. Its golden age peaked in the twelfth century.",
                                    "significance": "Medieval Caucasian power."},
            "Battle of Didgori": {"summary": "Didgori was fought in 1121 near Tbilisi. The Georgian coalition crushed the Seljuk host. The victory opened the way to Tbilisi's recapture.",
                                   "significance": "Decisive Georgian victory over the Seljuks."},
        },
        "self_audit": {"critic_iterations": 2, "orphan_check_done": True},
    }


def test_load_handoff_parses_and_coerces(tmp_path: Path):
    path = tmp_path / "candidates.json"
    path.write_text(json.dumps(_sample_doc()), encoding="utf-8")
    doc = load_handoff(path)
    assert doc.run_id == "campaign_test"
    assert len(doc.candidate_entities) == 3
    assert doc.summaries["David IV of Georgia"]["significance"].startswith("Broke")


def test_load_handoff_normalizes_synonym_types(tmp_path: Path):
    doc_dict = _sample_doc()
    doc_dict["candidate_entities"][1]["entity_type"] = "kingdom"
    path = tmp_path / "candidates.json"
    path.write_text(json.dumps(doc_dict), encoding="utf-8")
    doc = load_handoff(path)
    assert doc.candidate_entities[1].entity_type == "political_entity"


def test_hydrate_state_produces_full_tail_state(tmp_path: Path):
    path = tmp_path / "candidates.json"
    path.write_text(json.dumps(_sample_doc()), encoding="utf-8")
    doc = load_handoff(path)
    state = hydrate_state(doc, raw_input="raw transcript text")
    assert state["run_id"] == "campaign_test"
    assert state["title"] == "Test Chronicle"
    assert state["critic_done"] is True
    assert state["summaries_precomputed"] is True
    assert "David IV of Georgia" in state["summaries"]
    for key in ("parsed_events", "candidate_entities", "candidate_relations",
                "enriched_entities", "validation_results", "committed",
                "audit_log", "errors", "entity_id_map", "relation_id_map"):
        assert key in state


def test_hydrate_state_defaults_without_summaries(tmp_path: Path):
    doc_dict = _sample_doc()
    doc_dict["summaries_precomputed"] = False
    doc_dict["summaries"] = {}
    path = tmp_path / "candidates.json"
    path.write_text(json.dumps(doc_dict), encoding="utf-8")
    doc = load_handoff(path)
    state = hydrate_state(doc, raw_input="")
    assert state["summaries_precomputed"] is False
    assert state["summaries"] == {}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pipeline/.venv/bin/python -m pytest pipeline/agent/tests/test_handoff.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.agent.handoff'`

- [ ] **Step 4: Add state keys**

In `pipeline/agent/graph/state.py`, inside `AgentRunState`, after the `critic_iterations`/`critic_done` block add:

```python
    # Handoff mode (--from-candidates): pre-generated summaries keyed by entity
    # label, plus the flag telling generate_content to skip its LLM calls.
    summaries: dict[str, dict[str, str]]
    summaries_precomputed: bool
```

- [ ] **Step 5: Implement handoff.py**

```python
# pipeline/agent/handoff.py
"""Handoff-file loading for opencode-authored extractions.

An opencode session performs the graph's LLM stages offline (parse_sequence,
extract_candidates, completeness_critic, generate_content summaries) and writes
a candidates.json handoff file. load_handoff validates it against the pipeline
schemas; hydrate_state builds an AgentRunState ready for the deterministic tail
(db_lookup onward) via build_workflow(entry_point="tail").
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from pipeline.agent.schemas.entities import CandidateEntity, ParsedEvent
from pipeline.agent.schemas.relations import CandidateRelation


class HandoffDocument(BaseModel):
    run_id: str
    source_transcript: str | None = None
    title: str | None = None
    summaries_precomputed: bool = False
    parsed_events: list[ParsedEvent] = Field(default_factory=list)
    candidate_entities: list[CandidateEntity] = Field(default_factory=list)
    candidate_relations: list[CandidateRelation] = Field(default_factory=list)
    summaries: dict[str, dict[str, str]] = Field(default_factory=dict)
    self_audit: dict = Field(default_factory=dict)


def load_handoff(path: str | Path) -> HandoffDocument:
    return HandoffDocument.model_validate_json(Path(path).read_text(encoding="utf-8"))


def hydrate_state(
    doc: HandoffDocument,
    raw_input: str,
    create_chronicle: bool = True,
    refresh: bool = False,
) -> dict:
    """Build a complete AgentRunState dict from a validated handoff document."""
    return {
        "run_id": doc.run_id,
        "raw_input": raw_input,
        "date_hints": [],
        "parsed_events": doc.parsed_events,
        "candidate_entities": doc.candidate_entities,
        "candidate_relations": doc.candidate_relations,
        "enriched_entities": [],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "chronicle": None,
        "audit_log": [],
        "errors": [],
        "title": doc.title,
        "create_chronicle": create_chronicle,
        "refresh": refresh,
        "entity_id_map": {},
        "relation_id_map": {},
        "critic_iterations": int(doc.self_audit.get("critic_iterations", 0)),
        "critic_done": True,
        "summaries": doc.summaries,
        "summaries_precomputed": doc.summaries_precomputed,
    }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pipeline/.venv/bin/python -m pytest pipeline/agent/tests/test_handoff.py -v`
Expected: 4 PASS

- [ ] **Step 7: Commit**

```bash
git add pipeline/agent/handoff.py pipeline/agent/graph/state.py pipeline/agent/tests/test_handoff.py
git commit -m "feat(pipeline): handoff document loader + precomputed-summary state keys"
```

---

### Task 2: Tail entry point in build_workflow

**Files:**
- Modify: `pipeline/agent/graph/workflow.py:32-81`
- Test: `pipeline/agent/tests/test_graph.py`

- [ ] **Step 1: Impact analysis**

Impact on `build_workflow` (upstream): called by `run_agent`, `__main__.agent`, tests. Adding a keyword arg with default preserves all callers.

- [ ] **Step 2: Write the failing test**

Append to `pipeline/agent/tests/test_graph.py`:

```python
def test_build_workflow_tail_entry_point():
    workflow = build_workflow(entry_point="tail")
    graph = workflow.get_graph()
    nodes = {n for n in graph.nodes}
    assert "db_lookup" in nodes and "audit_logger" in nodes
    entries = {e.source for e in graph.edges if e.source == "__start__"}
    assert entries == {"db_lookup"}


def test_build_workflow_default_entry_unchanged():
    workflow = build_workflow()
    graph = workflow.get_graph()
    entries = {e.source for e in graph.edges if e.source == "__start__"}
    assert entries == {"preprocess_transcript"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pipeline/.venv/bin/python -m pytest pipeline/agent/tests/test_graph.py::test_build_workflow_tail_entry_point -v`
Expected: FAIL — TypeError unexpected keyword `entry_point`

- [ ] **Step 4: Implement**

In `workflow.py` change the signature and entry point line:

```python
def build_workflow(entry_point: str = "full") -> StateGraph:
    """Build and return the compiled agent workflow graph.

    entry_point="full" (default): complete graph starting at preprocess_transcript.
    entry_point="tail": starts at db_lookup — handoff runs where the LLM stages
    already executed offline (--from-candidates). Upstream nodes stay registered
    but are never reached from the tail entry point.
    """
```

and replace `workflow.set_entry_point("preprocess_transcript")` with:

```python
    workflow.set_entry_point(
        "preprocess_transcript" if entry_point == "full" else "db_lookup"
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pipeline/.venv/bin/python -m pytest pipeline/agent/tests/test_graph.py -v`
Expected: PASS (all existing + 2 new)

- [ ] **Step 6: Commit**

```bash
git add pipeline/agent/graph/workflow.py pipeline/agent/tests/test_graph.py
git commit -m "feat(pipeline): tail entry point for handoff-driven runs"
```

---

### Task 3: generate_content passthrough

**Files:**
- Modify: `pipeline/agent/graph/nodes/generate_content.py:145-263`
- Test: `pipeline/agent/tests/test_nodes_llm.py`

- [ ] **Step 1: Impact analysis**

Impact on `generate_content`: only edge is workflow wiring. Passthrough must keep audit-log emission so downstream manifest counts stay meaningful.

- [ ] **Step 2: Write the failing test**

Append to `test_nodes_llm.py` (match its existing imports/fixtures; build a minimal enriched state as other tests in that file do):

```python
def test_generate_content_passthrough_skips_llm():
    from pipeline.agent.graph.nodes.generate_content import generate_content
    from pipeline.agent.schemas.entities import CandidateEntity, EnrichedCandidate
    from pipeline.agent.schemas.relations import CandidateRelation

    entity = EnrichedCandidate(candidate=CandidateEntity(label="Athens", entity_type="city"))
    relation = CandidateRelation(source_label="Athens", target_label="Sparta",
                                 relationship_type="at_war_with", description="Long rivalry.")
    state = {
        "run_id": "t", "parsed_events": [], "enriched_entities": [entity],
        "candidate_relations": [relation],
        "title": "Given Title",
        "summaries_precomputed": True,
        "summaries": {"Athens": {"summary": "Athens was a Greek polis. It pioneered democracy. Its fleet ruled the Aegean.",
                                  "significance": "Cradle of democracy."}},
        "audit_log": [], "errors": [],
    }
    with patch("pipeline.agent.graph.nodes.generate_content.create_llm_with_fallbacks") as mk:
        result = generate_content(state)
        mk.assert_not_called()
    assert result["enriched_entities"][0].summary.startswith("Athens was a Greek polis")
    assert result["enriched_entities"][0].significance == "Cradle of democracy."
    assert any(a.action == "content_generated" for a in result["audit_log"])
```

And a gap-fill case (same state but `summaries: {}` and relation `description=None`):

```python
def test_generate_content_gapfill_uses_llm_for_missing():
    # entity without precomputed summary -> factory IS called, missing entity
    # receives summary/significance from the mocked response
    ...
    with patch("pipeline.agent.graph.nodes.generate_content.create_llm_with_fallbacks") as mk:
        mk.return_value = mock_llm  # invoke_json returns {"entities": {"Athens": {...}}}
        result = generate_content(state)
        mk.assert_called_once()
    assert result["enriched_entities"][0].summary is not None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pipeline/.venv/bin/python -m pytest pipeline/agent/tests/test_nodes_llm.py::test_generate_content_passthrough_skips_llm -v`
Expected: FAIL — factory currently invoked / summary empty

- [ ] **Step 4: Implement**

Restructure `generate_content` so LLM construction is lazy and the passthrough short-circuits:

```python
def generate_content(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    entities = state["enriched_entities"]
    relations = state["candidate_relations"]
    logger.info("generate_content (entities=%d, relations=%d)", len(entities), len(relations))

    event_text = _event_text_by_label(state["parsed_events"])
    rels_by_entity = _relations_by_entity(relations)
    by_label = {e.candidate.label: e for e in entities}

    llm = None  # lazily constructed; never built when everything is precomputed

    def _llm():
        nonlocal llm
        if llm is None:
            llm = create_llm_with_fallbacks("generate_model", cfg,
                                            max_tokens=cfg.generate_max_tokens,
                                            reasoning_effort=cfg.reasoning_effort)
        return llm

    pre_summaries = state.get("summaries") or {}
    if state.get("summaries_precomputed"):
        applied = _apply_precomputed_summaries(entities, pre_summaries)
        missing = [e.candidate.label for e in entities if not e.summary]
        logger.info("Handoff summaries applied to %d/%d entities (%d missing)",
                    applied, len(entities), len(missing))
        if missing:
            context = json.dumps(
                [_entity_context(e, event_text, rels_by_entity)
                 for e in entities if not e.summary],
                default=str,
            )
            prompt = _ENTITY_PROMPT.format(style_guide=_load_style_guide(), entities=context)
            _apply_summary_pass(_llm(), prompt, by_label, state, "summary_gapfill")
    else:
        for chunk in _chunked(entities, ENTITY_CHUNK_SIZE):
            context = json.dumps(
                [_entity_context(e, event_text, rels_by_entity) for e in chunk],
                default=str,
            )
            prompt = _ENTITY_PROMPT.format(style_guide=_load_style_guide(), entities=context)
            _apply_summary_pass(_llm(), prompt, by_label, state, "summary")

        deficient = [e for e in entities if _sentence_count(e.summary) < 3]
        if deficient:
            logger.info("Re-requesting %d short summaries (<3 sentences)", len(deficient))
            for chunk in _chunked(deficient, ENTITY_CHUNK_SIZE):
                context = json.dumps(
                    [_entity_context(e, event_text, rels_by_entity) for e in chunk],
                    default=str,
                )
                prompt = _ENTITY_PROMPT.format(style_guide=_load_style_guide(), entities=context) + (
                    "\n\nIMPORTANT: a previous attempt returned summaries that were too short. "
                    "Write a NEW summary of at least THREE full sentences for EVERY entity above."
                )
                _apply_summary_pass(_llm(), prompt, by_label, state, "summary_retry")

    if relations and any(not r.description for r in relations):
        relations_context = json.dumps(
            [
                {"source": r.source_label, "target": r.target_label, "type": r.relationship_type,
                 "dates": {"start": r.start_date, "end": r.end_date}}
                for r in relations if not r.description
            ],
            default=str,
        )
        rel_prompt = (
            "You are a historical content writer. Write one concise sentence describing each relationship, "
            "grounded in the entities and dates given.\n\n"
            f"Relations:\n{relations_context}\n\n"
            'Output strictly as JSON:\n{"relation_descriptions": {"Source|relationship_type|Target": "..."}}\n'
        )
        try:
            data = _llm().invoke_json(
                [HumanMessage(content=rel_prompt)],
                validate=lambda d: isinstance(d, dict) and "relation_descriptions" in d,
            )
            rel_descs = data.get("relation_descriptions", {})
            for relation in relations:
                if relation.description:
                    continue
                key = f"{relation.source_label}|{relation.relationship_type}|{relation.target_label}"
                relation.description = rel_descs.get(key)
        except Exception as exc:
            state["errors"].append(
                PipelineError(node="generate_content", error_type="json_parse",
                              message=str(exc), context={"stage": "relation_descriptions"})
            )

    if not (state.get("title") or "").strip() and entities:
        names = ", ".join(e.candidate.label for e in entities[:14])
        title_prompt = (
            "Write ONE engaging, specific title for a historical chronicle that covers these entities:\n"
            f"{names}\n\n"
            "Make it evocative yet accurate, like 'The Rise and Fall of the Byzantine Empire', 'Plagues That "
            "Reshaped the Ancient World', or 'How the Silk Road Bound East to West'. Max 9 words, no subtitle.\n"
            'Output strictly as JSON: {"title": "..."}'
        )
        try:
            data = _llm().invoke_json(
                [HumanMessage(content=title_prompt)],
                validate=lambda d: isinstance(d, dict) and "title" in d,
            )
            title = (data.get("title") or "").strip()
            if title:
                state["title"] = title
                logger.info("Generated chronicle title: %s", title)
        except Exception as exc:
            state["errors"].append(
                PipelineError(node="generate_content", error_type="json_parse",
                              message=str(exc), context={"stage": "title"})
            )

    summarised = sum(1 for e in entities if e.summary)
    with_significance = sum(1 for e in entities if e.significance)
    state["audit_log"].append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="generate_content",
            action="content_generated",
            output_summary=(
                f"{summarised}/{len(entities)} summaries, {with_significance} significance, "
                f"{len(relations)} relations"
            ),
        )
    )
    return state
```

Plus the helper:

```python
def _apply_precomputed_summaries(entities: list, summaries: dict[str, dict[str, str]]) -> int:
    """Apply handoff-authored summary/significance onto enriched candidates."""
    applied = 0
    for e in entities:
        fields = summaries.get(e.candidate.label)
        if not isinstance(fields, dict):
            continue
        if fields.get("summary") and not e.summary:
            e.summary = fields["summary"]
        if fields.get("significance") and not e.significance:
            e.significance = fields["significance"]
        if e.summary:
            applied += 1
    return applied
```

- [ ] **Step 5: Run full agent suite**

Run: `pipeline/.venv/bin/python -m pytest pipeline/agent/tests/ -v`
Expected: PASS — including pre-existing `test_run_agent_end_to_end`

- [ ] **Step 6: Commit**

```bash
git add pipeline/agent/graph/nodes/generate_content.py pipeline/agent/tests/test_nodes_llm.py
git commit -m "feat(pipeline): precomputed-summary passthrough in generate_content"
```

---

### Task 4: --from-candidates CLI

**Files:**
- Modify: `pipeline/agent/graph/workflow.py` (add `run_agent_from_candidates`)
- Modify: `pipeline/agent/__main__.py:16-21`
- Test: `pipeline/agent/tests/test_graph.py`

- [ ] **Step 1: Impact analysis**

New function + one click option; no symbol modified.

- [ ] **Step 2: Write the failing test**

Append to `test_graph.py`:

```python
@patch("pipeline.agent.llm.ChatOpenAI")
@patch("pipeline.agent.graph.nodes.db_lookup.search_entity_by_name")
@patch("pipeline.agent.graph.nodes.resolve_wikidata.search_wikidata_by_name")
@patch("pipeline.agent.graph.nodes.resolve_wikidata.enrich_wikidata_entities")
@patch("pipeline.agent.graph.nodes.resolve_ohm.resolve_polity")
@patch("pipeline.agent.graph.nodes.commit_writer.run_artisan_command")
def test_run_agent_from_candidates_end_to_end(mock_run, mock_resolve_polity, mock_enrich,
                                              mock_wd, mock_db, mock_chat, tmp_path):
    """The sample handoff is fully precomputed (summaries + descriptions + title),
    so the tail must run WITHOUT constructing any LLM."""
    from pipeline.agent.graph.workflow import run_agent_from_candidates
    from pipeline.agent.tests.test_handoff import _sample_doc

    mock_db.return_value = []
    mock_wd.return_value = [{"qid": "Q405", "label": "David IV of Georgia", "description": "King"}]
    mock_enrich.return_value = {"Q405": {"label": "David IV of Georgia", "description": "King"}}
    mock_resolve_polity.return_value = None
    mock_run.return_value = {"returncode": 0, "stdout": "OK", "stderr": ""}

    handoff_path = tmp_path / "candidates.json"
    handoff_path.write_text(json.dumps(_sample_doc()), encoding="utf-8")

    cfg = AgentConfig()
    prev = Path(cfg.output_dir) / "campaign_test"
    if prev.exists():
        shutil.rmtree(prev)

    result = run_agent_from_candidates(str(handoff_path))
    assert result["run_id"] == "campaign_test"
    assert len(result["enriched_entities"]) == 3
    assert all(e.summary and e.significance for e in result["enriched_entities"])
    assert result["errors"] == []
    mock_chat.assert_not_called()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pipeline/.venv/bin/python -m pytest pipeline/agent/tests/test_graph.py::test_run_agent_from_candidates_end_to_end -v`
Expected: FAIL — ImportError `run_agent_from_candidates`

- [ ] **Step 4: Implement run_agent_from_candidates**

In `workflow.py`:

```python
def run_agent_from_candidates(handoff_path, run_id=None, create_chronicle=True, refresh=False) -> AgentRunState:
    """Run the deterministic tail from an opencode-authored handoff file.

    See docs/superpowers/specs/2026-08-23-history-data-campaign-design.md §4–§5.
    Idempotency mirrors run_agent(): a clean existing manifest short-circuits.
    """
    import os
    from pipeline.agent.handoff import hydrate_state, load_handoff

    cfg = AgentConfig()
    doc = load_handoff(handoff_path)
    run_id = run_id or doc.run_id

    output_root = Path(cfg.output_dir) / run_id
    manifest_path = output_root / "manifest.json"
    if not refresh and manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
        if manifest.get("errors_count", 0) == 0:
            logger.info("Run %s already completed successfully, skipping", run_id)
            return {"run_id": run_id, "raw_input": "", "parsed_events": doc.parsed_events,
                    "candidate_entities": doc.candidate_entities,
                    "candidate_relations": doc.candidate_relations,
                    "enriched_entities": [], "validation_results": [],
                    "proposed_diff": None, "committed": [], "chronicle": None,
                    "audit_log": [], "errors": [], "title": doc.title,
                    "create_chronicle": create_chronicle, "entity_id_map": {},
                    "relation_id_map": {}, "critic_iterations": 0, "critic_done": True}

    raw_input = ""
    if doc.source_transcript and os.path.exists(doc.source_transcript):
        raw_input = Path(doc.source_transcript).read_text(encoding="utf-8")

    initial_state = hydrate_state(doc, raw_input=raw_input,
                                  create_chronicle=create_chronicle, refresh=refresh)
    initial_state["run_id"] = run_id

    workflow = build_workflow(entry_point="tail")
    result = workflow.invoke(initial_state, config={"configurable": {"thread_id": run_id}})
    logger.info("Handoff workflow complete: run_id=%s errors=%d committed=%d",
                run_id, len(result.get("errors", [])), len(result.get("committed", [])))
    return result
```

- [ ] **Step 5: Add CLI option**

In `pipeline/agent/__main__.py` extend the command (keep `--input` optional when `--from-candidates` given):

```python
@click.option("--input", "input_path", type=click.Path(exists=True, path_type=Path), default=None, help="Path to raw historical text input file")
@click.option("--from-candidates", "from_candidates", type=click.Path(exists=True, path_type=Path), default=None, help="Path to an opencode-authored candidates.json handoff file (runs the deterministic tail)")
```

and at the top of the body:

```python
if from_candidates:
    from pipeline.agent.graph.workflow import run_agent_from_candidates
    run_id = run_id or from_candidates.parent.name
    click.echo(f"Starting handoff run: {run_id}{' [REFRESH]' if refresh else ''}")
    result = run_agent_from_candidates(str(from_candidates), run_id=run_id,
                                       create_chronicle=create_chronicle, refresh=refresh)
    _echo_result(result)   # extract the existing echo block into this helper
    return

if input_path is None:
    raise click.UsageError("Provide --input <transcript.txt> or --from-candidates <candidates.json>")
```

Refactor the shared echo block into `_echo_result(result)` used by both paths. Remove the `required=True` from `--input`.

- [ ] **Step 6: Run tests + CLI smoke**

Run: `pipeline/.venv/bin/python -m pytest pipeline/agent/tests/test_graph.py pipeline/agent/tests/test_handoff.py -v`
Expected: PASS

Run: `pipeline/.venv/bin/python -m pipeline agent --help | grep from-candidates`
Expected: option listed

- [ ] **Step 7: Commit**

```bash
git add pipeline/agent/graph/workflow.py pipeline/agent/__main__.py pipeline/agent/tests/test_graph.py
git commit -m "feat(pipeline): --from-candidates handoff mode for the agent CLI"
```

---

### Task 5: validate_handoff gate CLI

**Files:**
- Create: `pipeline/agent/validate_handoff.py`
- Test: `pipeline/agent/tests/test_validate_handoff.py`

- [ ] **Step 1: Write the failing test**

```python
# pipeline/agent/tests/test_validate_handoff.py
import json
from pathlib import Path

from pipeline.agent.validate_handoff import main
from pipeline.agent.tests.test_handoff import _sample_doc


def _write(tmp_path, mutate=None):
    doc = _sample_doc()
    if mutate:
        mutate(doc)
    p = tmp_path / "candidates.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return str(p)


def test_valid_handoff_passes(tmp_path, capsys):
    assert main(_write(tmp_path)) == 0
    assert "OK" in capsys.readouterr().out


def test_orphan_relation_endpoint_fails(tmp_path):
    def mutate(doc):
        doc["candidate_relations"][0]["target_label"] = "Ghost Entity"
    assert main(_write(tmp_path, mutate)) == 1


def test_disallowed_relation_type_fails(tmp_path):
    def mutate(doc):
        doc["candidate_relations"][0]["relationship_type"] = "knows"
    assert main(_write(tmp_path, mutate)) == 1


def test_missing_summary_fails_when_precomputed(tmp_path):
    def mutate(doc):
        doc["summaries"] = {}
    assert main(_write(tmp_path, mutate)) == 1


def test_reversed_dates_fail(tmp_path):
    def mutate(doc):
        doc["candidate_entities"][0]["start_date"] = "1125"
        doc["candidate_entities"][0]["end_date"] = "1073"
    assert main(_write(tmp_path, mutate)) == 1


def test_era_bounds_checked_when_encoded_in_filename(tmp_path):
    p = tmp_path / "e04__x" / "candidates.json"
    p.mkdir(parent=True)
    doc = _sample_doc()
    doc["candidate_entities"][0]["start_date"] = "-3000"
    p.write_text(json.dumps(doc), encoding="utf-8")
    assert main(str(p)) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pipeline/.venv/bin/python -m pytest pipeline/agent/tests/test_validate_handoff.py -v`
Expected: FAIL — module missing

- [ ] **Step 3: Implement**

```python
# pipeline/agent/validate_handoff.py
"""Fail-fast validation gate for opencode extraction handoffs.

Checks (spec §4.2): schema parse, canonical entity types, allowed relation
types, referential integrity, summary completeness when precomputed, date
sanity (start <= end, year within the era bounds implied by the filename).

Usage: python -m pipeline.agent.validate_handoff <path/to/candidates.json>
Exit 0 = clean; exit 1 = itemised errors on stderr/stdout.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from pipeline.agent.graph.nodes.validate import ALLOWED_RELATION_TYPES
from pipeline.agent.handoff import load_handoff
from pipeline.agent.schemas.entities import _CANONICAL_ENTITY_TYPES

ERA_BOUNDS = {
    "e01": (-9000, -4000),
    "e02": (-4000, -1200),
    "e03": (-1200, -750),
    "e04": (-750, -330),
    "e05": (-330, -30),
    "e06": (-30, 500),
    "e07": (500, 1000),
    "e08": (1000, 1350),
    "e09": (1350, 1750),
    "e10": (1750, 2000),
}


def _year(date_str: str | None) -> int | None:
    if not date_str:
        return None
    m = re.match(r"^(-?\d{1,5})", date_str.strip())
    return int(m.group(1)) if m else None


def validate(path: str | Path) -> list[str]:
    errors: list[str] = []
    try:
        doc = load_handoff(path)
    except Exception as exc:
        return [f"schema parse failed: {exc}"]

    labels = {c.label for c in doc.candidate_entities}
    for c in doc.candidate_entities:
        if c.entity_type not in _CANONICAL_ENTITY_TYPES:
            errors.append(f"entity '{c.label}': non-canonical type '{c.entity_type}'")
        sy, ey = _year(c.start_date), _year(c.end_date)
        if sy is not None and ey is not None and sy > ey:
            errors.append(f"entity '{c.label}': start_year {sy} > end_year {ey}")
        for y in (sy, ey):
            if y is not None and not -10000 < y <= 2100:
                errors.append(f"entity '{c.label}': implausible year {y}")

    for r in doc.candidate_relations:
        if r.relationship_type not in ALLOWED_RELATION_TYPES:
            errors.append(f"relation {r.source_label}->{r.target_label}: "
                          f"disallowed type '{r.relationship_type}'")
        for endpoint in (r.source_label, r.target_label):
            if endpoint not in labels:
                errors.append(f"relation endpoint '{endpoint}' has no extracted entity")

    if doc.summaries_precomputed:
        for c in doc.candidate_entities:
            fields = doc.summaries.get(c.label) or {}
            if not (fields.get("summary") or "").strip() or not (fields.get("significance") or "").strip():
                errors.append(f"entity '{c.label}': missing summary/significance "
                              f"(summaries_precomputed=true)")

    era_match = re.match(r"e(\d{2})", Path(str(path)).parent.name.lower()) or \
        re.search(r"\be(\d{2})\b", Path(str(path)).name.lower())
    if era_match:
        key = f"e{era_match.group(1)}"
        lo, hi = ERA_BOUNDS[key]
        for c in doc.candidate_entities:
            for y in (_year(c.start_date), _year(c.end_date)):
                if y is not None and not (lo <= y <= hi):
                    errors.append(f"entity '{c.label}': year {y} outside {key} bounds [{lo}, {hi}]")
    return errors


def main(path: str) -> int:
    errors = validate(path)
    if errors:
        print(f"INVALID handoff {path}: {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK {path}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m pipeline.agent.validate_handoff <candidates.json>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
```

(The era-bounds test relies on the parent directory name encoding the era — `e04__x/candidates.json` → E04 bounds `[-750, -330]`, so `-3000` fails. A handoff without an era-encoded path skips that check.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pipeline/.venv/bin/python -m pytest pipeline/agent/tests/test_validate_handoff.py -v`
Expected: 6 PASS

- [ ] **Step 5: Full suite green**

Run: `pipeline/.venv/bin/python -m pytest pipeline/agent/tests/ pipeline/tests/ -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add pipeline/agent/validate_handoff.py pipeline/agent/tests/test_validate_handoff.py
git commit -m "feat(pipeline): fail-fast validation gate for extraction handoffs"
```

---

### Task 6: Campaign driver script

**Files:**
- Create: `run_campaign.sh` (repo root, sibling of `run_all_transcripts.sh`)

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# Process pending opencode extraction handoffs through the deterministic tail.
# Usage: bash run_campaign.sh 2>&1 | tee /tmp/campaign_run.log
set -euo pipefail
cd "$(dirname "$0")"

VENV=pipeline/.venv/bin/python
EXTRACTIONS_DIR=${EXTRACTIONS_DIR:-output/campaign/extractions}
SUMMARY=${CAMPAIGN_SUMMARY:-/tmp/campaign_summary.txt}
: > "$SUMMARY"

TOTAL=0; OK=0; FAILED=0
for HANDOFF in "$EXTRACTIONS_DIR"/*/candidates.json; do
    [ -f "$HANDOFF" ] || continue
    TOTAL=$((TOTAL + 1))
    RUN_ID=$(basename "$(dirname "$HANDOFF")")
    echo ""
    echo "[$TOTAL] START $RUN_ID at $(date)"

    if ! OUT=$("$VENV" -m pipeline.agent.validate_handoff "$HANDOFF" 2>&1); then
        echo "$OUT"
        echo "[$RUN_ID] INVALID handoff (see above)" >> "$SUMMARY"
        FAILED=$((FAILED + 1))
        continue
    fi

    # EXTRA_AGENT_FLAGS lets re-runs pass e.g. --refresh.
    if OUT=$("$VENV" -m pipeline agent --from-candidates "$HANDOFF" --run-id "$RUN_ID" ${EXTRA_AGENT_FLAGS:-} 2>&1); then
        OK=$((OK + 1))
        echo "[$RUN_ID] OK"
        echo "[$RUN_ID] ok" >> "$SUMMARY"
    else
        FAILED=$((FAILED + 1))
        echo "$OUT" | tail -20
        echo "[$RUN_ID] ERR" >> "$SUMMARY"
    fi
done

echo ""
echo "=== campaign: $TOTAL total, $OK ok, $FAILED failed at $(date) ===" | tee -a "$SUMMARY"
```

- [ ] **Step 2: Smoke test the loop logic**

Create a throwaway invalid handoff under `/tmp/opencode/fake_extractions/bad/candidates.json`, run with `EXTRACTIONS_DIR=/tmp/opencode/fake_extractions`, expect `INVALID handoff` line and non-zero failures count in summary.

- [ ] **Step 3: Commit**

```bash
git add run_campaign.sh
git commit -m "chore(pipeline): campaign driver for handoff batch ingestion"
```

---

### Task 7: Environment bring-up (operational)

- [ ] **Step 1: Start stack** — `docker compose -f docker/docker-compose.yml up -d`; wait until `app` and `db` report running.
- [ ] **Step 2: Fresh DB** — `docker compose -f docker/docker-compose.yml exec app php artisan migrate:fresh --force` (fresh-start decision; June dump remains at `output/history-mapped.sql`).
- [ ] **Step 3: Verify venv** — `pipeline/.venv/bin/python -m pytest pipeline/agent/tests/ -q` green.

No commit (environment only).

---

### Task 8: Wave 0 — author pilot transcripts

**Files (create):**
- `output/transcripts/campaign/e01__mesopotamia__neolithic-settlements.txt`
- `output/transcripts/campaign/e04__aegean__classical-greece.txt`
- `output/transcripts/campaign/e10__global__modern-revolutions.txt`

Authored by opencode following spec §3.3 authoring rules: numbered facts; explicit BCE/CE years with `c.` where approximate; relationship-rich phrasing; canonical English labels + aliases; 60–150 facts each; era tie-break rule (an era owns its start year).

- [ ] **Step 1: Author the three files** (content work — dispatch extraction subagents per spec §4).
- [ ] **Step 2: Self-review each file against §3.3 checklist** (dates signed, no fabricated month/day, actors named, relationships explicit).
- [ ] **Step 3: Commit transcripts.**

```bash
git add output/transcripts/campaign/
git commit -m "docs(data): wave-0 pilot transcripts (neolithic, classical greece, modern revolutions)"
```

---

### Task 9: Wave 0 — extract, ingest, measure

- [ ] **Step 1: Produce handoffs** — one extraction session per pilot transcript writing `output/campaign/extractions/<run_id>/candidates.json` (run_ids: `campaign_e01__mesopotamia__neolithic-settlements`, etc.). Extraction binds to schemas per spec §4.1, includes critic self-loop + G3 referential integrity + style-guide summaries.
- [ ] **Step 2: Validate** — `pipeline/.venv/bin/python -m pipeline.agent.validate_handoff output/campaign/extractions/<run_id>/candidates.json` → OK ×3 (fix-and-reloop on failure).
- [ ] **Step 3: Ingest** — `bash run_campaign.sh`.
- [ ] **Step 4: Verify imports landed**

```bash
docker compose -f docker/docker-compose.yml exec -T db psql -U history-mapped -d history-mapped \
  -c "SELECT count(*) AS entities FROM entities;" \
  -c "SELECT entity_type, count(*) FROM entities GROUP BY 1 ORDER BY 2 DESC LIMIT 15;" \
  -c "SELECT count(*) AS chronicles FROM chronicles;"
```

Expected: hundreds of entities across ≥6 types; 3 chronicles.

(If psql auth fails, check `POSTGRES_USER`/`POSTGRES_DB` in `docker/docker-compose.yml` — defaults are `history-mapped`/`history-mapped`.)

- [ ] **Step 5: Acceptance measurement** — adapt the §2 queries from `docs/plans/pipeline-data-quality-remediation.md` (georef distribution by group, `-01-01` fabrication count, orphan rate, chronicle impact spread) against the pilot rows. Compare against the acceptance table (spec §7). Any red metric → diagnose before mass authoring (this is the Wave-0 gate).

- [ ] **Step 6: Record results** — append measured numbers + go/no-go to this plan file's Task 9 section; commit.

---

### Task 10: Docs update

**Files:**
- Modify: `docs/implementation-docs/agentic-pipeline-runbook.md` (new "Handoff mode" section documenting `--from-candidates`, handoff contract pointer, validate CLI, driver usage)
- Modify: `README.md` Data Pipeline section (one-line pointer to handoff mode + campaign driver)

- [ ] **Step 1: Write both doc updates.**
- [ ] **Step 2: Commit** — `git commit -m "docs(pipeline): document opencode handoff mode and campaign driver"`

---

## Post-plan execution (the campaign itself)

Tasks 1–7 = machinery. Tasks 8–9 = pilot gate. On green pilot, the campaign proceeds by repetition, NOT new code:

1. **Wave 1 backbone (~60 transcripts)** — authored + extracted via parallel subagent batches (10–20 transcripts each), ingested via `run_campaign.sh`, acceptance queries re-run per wave.
2. **Wave 2 fine grid (~240 transcripts)** — same cadence.
3. **Per-wave repair** — `merge_entities`, `reresolve_entities --apply Name=QID`, `php artisan entity:backfill --entity-id=<id>` for stragglers.
4. **Post-campaign** — embeddings (`pipeline:embeddings`) as a separate follow-up; final §2 re-measure archived into the remediation doc's protocol.

Verification commands for every code task: `pipeline/.venv/bin/python -m pytest pipeline/agent/tests/ -v` (full suite before declaring done), plus lint-equivalents if configured (`ruff` not currently set up for pipeline — do not introduce).
