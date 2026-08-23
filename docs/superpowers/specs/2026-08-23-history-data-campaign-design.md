# History Data Campaign — Design Spec

> **Date:** 2026-08-23
> **Status:** Draft for review
> **Scope:** Mass data generation campaign for `history-mapped`: well-established historical facts from 9000 BCE to 2000 CE, produced by opencode (ox-alpha) driving the existing LangGraph agentic pipeline.
> **Related docs:**
> - [agentic-pipeline-runbook.md](../../implementation-docs/agentic-pipeline-runbook.md) — pipeline architecture reference
> - [pipeline-data-quality-remediation.md](../../plans/pipeline-data-quality-remediation.md) — baseline defects and re-measure protocol (§2, §6)
> - [entity-reresolution.md](../../implementation-docs/entity-reresolution.md) — repair tooling for committed rows

---

## 1. Goal

Populate the atlas with comprehensive, high-quality entity/relation/geo/chronicle data covering **all well-established historical facts from 9000 BCE to 2000 CE**, at a scale far beyond the current ~884-entity dataset (~30k facts authored, targeting thousands of unique entities after dedup), using opencode sessions (unlimited ox-alpha) as the LLM half and the existing deterministic pipeline half for enrichment, validation, and import.

## 2. Decisions (agreed during brainstorming)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | **Hybrid** — opencode authors corpus + does all LLM steps; LangGraph runs its deterministic half unchanged | Keeps Wikidata/OHM/dedup/validate/import machinery; unlimited ox-alpha removes rate-limit lottery that broke the June free-tier batch |
| Harness wiring | **Handoff files** (`candidates.json` → new `--from-candidates` resume entry) | No HTTP shim fragility, no OpenRouter quota, fail-fast schema validation at authoring time |
| Corpus scale | **Fine grid, ~300 transcripts** (~30k facts) | User wants maximum coverage; waves keep it tractable |
| DB baseline | **Fresh start** (`migrate:fresh`, no seed) | Existing rows carry documented free-model defects (wrong QIDs, `-753` over-anchors, split entities); June dump stays in `output/history-mapped.sql` |
| Chronicles | **One chronicle per transcript**, auto-imported | Matches pipeline design + SPA chronicle player; write path verified working (`chronicle_writer.py:39`) |

Explicitly rejected alternatives:
- *OpenRouter direct* (`stealth/ox-alpha` via API): smallest change but re-introduces rate/availability risk and burns quota unnecessarily.
- *Shim server* (OpenAI-compatible endpoint spawning `opencode run`): zero pipeline changes but process-spawn latency × ~10⁴ calls and brittle JSON-over-text channel.
- *Me replacing the graph entirely*: loses P31-aware Wikidata resolution, OHM geo, db dedup, type validation, importer plumbing.

## 3. Corpus design

Location: `output/transcripts/campaign/<era>__<topic>.txt`. Kebab-case topics. Same list-style format the parser was tuned on (numbered events/facts; explicit BCE/CE years; modern-country hints in parentheses; relationship-rich sentences).

### 3.1 Grid

**Eras (10):**

| ID | Era | Span |
|----|-----|------|
| E01 | Neolithic & Chalcolithic | 9000–4000 BCE |
| E02 | Bronze Age | 4000–1200 BCE |
| E03 | Early Iron Age | 1200–750 BCE |
| E04 | Archaic & Classical | 750–330 BCE |
| E05 | Hellenistic | 330–30 BCE |
| E06 | Roman & Imperial | 30 BCE–500 CE |
| E07 | Late Antique & Early Medieval | 500–1000 CE |
| E08 | High Medieval | 1000–1350 CE |
| E09 | Renaissance & Early Modern | 1350–1750 CE |
| E10 | Modern | 1750–2000 CE |

**Region tracks (~13):** Mesopotamia; Egypt & Nubia; Levant & Arabia; Anatolia & Aegean; Iran & Central Asia; South Asia; China; Korea/Japan/SE Asia; Sub-Saharan Africa; Europe North & West; Mediterranean Europe; Americas; Oceania & Pacific.

**Thematic overlays (~20):** Silk Road; trans-Saharan trade; Indian Ocean trade; spread of Buddhism; spread of Christianity; rise of Islam; major wars (per era); epidemics; technology diffusion; migrations; revolutions; etc.

Cells are populated only where historically meaningful (not every era × region is dense). Driver manifest records expected fact count per file (~60–150). Total ≈ 300 files ≈ 30k facts. Era boundary years (e.g. 330 BCE in E04 and E05) resolve by the tie-break: **an era owns its start year** — a fact dated exactly at the boundary belongs to the later era's transcript.

### 3.2 Waves

1. **Wave 0 — Pilot (3 files).** Hardest cases first: one BCE-heavy Neolithic file, one namesake-dense Classical Greek file, one modern-era file. Runs end-to-end against real Docker+DB before any mass authoring. Gate: pilot passes acceptance table (§7).
2. **Wave 1 — Backbone (~60 files).** One transcript per era × macro-region (6 macro-regions) covering highest-signal polities/events/people. Purpose: establish dedup anchors in `db_lookup` before fine-grained regional runs arrive.
3. **Wave 2 — Fine grid remainder (~240 files).** Full regional depth + thematic overlays.

Ordering matters: backbone-first minimises cross-wave duplicate rows; remaining dupes handled post-campaign with `merge_entities`.

### 3.3 Authoring quality rules

- Only **well-established** facts (textbook consensus); contested claims either omitted or explicitly hedged ("traditionally dated", "disputed").
- Dates: explicit year + BCE/CE on every fact; `c.` prefix when approximate. No month/day unless genuinely known (prevents fabricated precision — remediation P2/F3).
- Every fact names its actors (persons/polities/places) with canonical common English labels; aliases included where names vary ("Ashoka / Asoka").
- Relationship-rich phrasing: "X defeated Y at Z", "X succeeded Y", "X built Y in Z" — these become relations.
- No QIDs, no coordinates, no confidence numbers in transcripts — enrichment is the pipeline's job.

## 4. Extraction protocol

Per transcript, an opencode session dispatches subagents in batches of ~10–20 transcripts. Each extraction:

1. Applies the exact prompt intent of the graph's LLM nodes — `parse_sequence`, `extract_candidates`, `completeness_critic` (including its recall self-loop and the G3 referential-integrity rule: never emit a relation whose endpoints aren't also extracted) — reading the prompts from `pipeline/agent/graph/nodes/*.py` as the normative specification.
2. Pre-generates `summary` and `significance` per entity following `pipeline/agent/style_guide.md`.
3. Emits a handoff file (below).

### 4.1 Handoff contract

Path: `output/campaign/extractions/<run_id>/candidates.json`

```json
{
  "run_id": "campaign_e04__aegean_classical",
  "source_transcript": "output/transcripts/campaign/e04__aegean__classical-greece.txt",
  "title": "Classical Aegean, 750–330 BCE",
  "summaries_precomputed": true,
  "parsed_events": [ { "label": "...", "description": "...", "start_date": "-750", "end_date": null, "mentioned_entities": ["..."], "date_uncertain": false } ],
  "candidate_entities": [ { "label": "Athens", "entity_type": "political_entity", "start_date": "-750", "end_date": null, "source_event": "...", "aliases": ["..."], "wikidata_id": null, "confidence": 0.0 } ],
  "candidate_relations": [ { "source_label": "Athens", "target_label": "Sparta", "relationship_type": "at_war_with", "start_date": "-431", "end_date": "-404", "source_event": "...", "description": "...", "confidence": 0.0 } ],
  "summaries": { "Athens": { "summary": "...", "significance": "..." } },
  "self_audit": { "critic_iterations": 2, "orphan_check_done": true }
}
```

Binding rules:
- Item shapes are exactly `ParsedEvent`, `CandidateEntity`, `CandidateRelation` from `pipeline/agent/schemas/entities.py` / `relations.py` (pydantic). Type normalisation (`normalize_entity_type`) happens at model construction, same as the live nodes.
- Pre-generated prose lives in a top-level `"summaries"` map keyed by entity label: `{ "<label>": { "summary": str, "significance": str } }`. (`CandidateEntity` has no such fields by design; pydantic ignores extra keys, so the validation gate checks this map explicitly.) `summaries_precomputed: true` requires every candidate label to appear in the map with both values non-empty.
- `entity_type` values should already be canonical (the taxonomy in `schemas/entities.py:_CANONICAL_ENTITY_TYPES`); `relationship_type` values must be in `validate.ALLOWED_RELATION_TYPES`.
- Years as strings matching the existing date convention (`"-331"` = 331 BCE); sign errors are the #1 historical defect class (remediation F2) — extractions double-check CE/BCE polarity.
- `wikidata_id` stays `null`. Extraction never fabricates QIDs or geometry.
- `self_audit` is provenance metadata only — recorded in the run manifest, consumed by no node.

### 4.2 Validation gate

New thin CLI module `pipeline.agent.validate_handoff`:

```
python -m pipeline.agent.validate_handoff output/campaign/extractions/<run_id>/candidates.json
```

Checks: pydantic parse of every list item; canonical types; allowed relation types; referential integrity (every relation endpoint label resolves to an extracted entity); summaries present when `summaries_precomputed`; date sanity (`start_year ≤ end_year`, plausible span, correct sign vs era hint from filename). Non-zero exit with itemised errors. The fixing agent re-emits until clean. This replaces `FallbackLLM.invoke_json`'s retry role at authoring time.

## 5. Pipeline changes

Minimal and surgical — the full-graph path remains the default and untouched.

1. **`build_workflow(entry="full"|"db_lookup")`** parameterises the compiled graph's entry point so a second variant starts at `db_lookup` and flows through the unchanged deterministic tail (`db_lookup → resolve_wikidata → resolve_ohm → generate_content → validate → build_diff → approval_gate → commit_writer → resolve_entity_ids → chronicle_builder → chronicle_writer → audit_logger`). Conditional critic edges exist only in the full variant.
2. **CLI**: `python -m pipeline agent --from-candidates PATH [--run-id ...]` hydrates `AgentRunState` from the handoff file (events, entities→`CandidateEntity`, relations, title; plus per-entity `summary`/`significance` carried through hydration into the enriched entries) and invokes the tail variant. Idempotent manifest-skip behaviour identical to `run_agent()`.
3. **`generate_content` passthrough**: when hydrated state marks `summaries_precomputed` and every enriched entry has summary+significance, the node skips its LLM call entirely (gap-fill only if an entry is missing text). Relation descriptions ride in from the handoff.
4. Nothing else changes. GitNexus impact analysis runs before touching any symbol; TDD throughout.

## 6. Runtime operations

1. `docker compose -f docker/docker-compose.yml up -d`
2. `migrate:fresh --force` (clean slate; June dump preserved at `output/history-mapped.sql`)
3. Campaign driver script (`run_campaign.sh`, sibling of `run_all_transcripts.sh`):
   for each pending run_id → validate handoff → `pipeline/.venv/bin/python -m pipeline agent --from-candidates ... --run-id <id>` sequentially.
   Sequential by design: respects configured Wikidata rate limit (30/min), serialises artisan imports.
   Skips runs with clean manifests (existing idempotency); failures appended to a campaign summary log.
4. Chronicles import automatically via the fixed write path; driver verifies `chronicles:import` return codes surface in manifests.

## 7. Quality gates & acceptance

Re-run the remediation doc's §2 measurement queries after each wave:

| Metric | Baseline (June free models) | Acceptance |
|--------|------------------------------|------------|
| PLACE entities with geo-ref | 0% | >80% |
| Fabricated `-01-01` dates on year-only facts | ~100% | ~0 |
| CE/BCE sign errors | intermittent | 0 found in spot-checks |
| Orphan entities | 48% | <15% |
| Relations resolved at import | ~50% (current code path with G3 fix measured ~94%) | >90% |
| Chronicle impact distinct values | 4 | >10 |
| Off-taxonomy types blocked | ~20% | 0 |

Additional per-wave checks:
- Random 20-entity spot-check against Wikidata (QID correctness, type, dates) performed by opencode before a wave is declared done.
- Repair passes for stragglers: `merge_entities` (duplicate splits), `reresolve_entities --apply Name=QID` (stubborn mis-resolutions), then `entity:backfill --entity-id=<id>`.

## 8. Testing

- **TDD on resume entry**: failing test first in `pipeline/agent/tests/test_graph.py` pattern (mocked nodes): hydration produces valid state; tail variant compiles; `--from-candidates` end-to-end with mocked deterministic nodes commits expected JSONL keys.
- **Validation gate tests**: valid handoff passes; each defect class (bad type, disallowed relation, orphan endpoint, missing summary, reversed dates, wrong-sign year) fails with actionable message.
- **Pilot gate**: Wave 0 runs against real Docker + Postgres; acceptance table green before mass authoring.
- Full suites green: `pytest pipeline/tests/ pipeline/agent/tests/`; Laravel side untouched but `php artisan test` run once after pilot imports.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Extraction drifts from schema expectations | Pydantic validation gate before graph tail; subagent instructions bind to schemas not prose |
| Session context limits across 300 transcripts | Stateless handoff files; batches of 10–20 per subagent; driver consumes artifacts independently |
| Cross-wave duplicates (Carthage-class splits) | Backbone-first ordering; importer dedup (QID/OHM/name+type+era); post-wave merge pass |
| Wikidata throttling over long tails | Sequential driver; configured 30 req/min; per-node timeouts already bound hangs |
| Era boundary facts double-counted (e.g. 330 BCE in E04 and E05) | Authoring rule: each fact lives in exactly one transcript; cross-references by label only |
| Handoff/summary drift between extraction and generate_content passthrough | Passthrough validates presence and falls back to gap-fill generation only when safe |

## 10. Out of scope

- Embedding generation (`pipeline:embeddings`) — separate step after campaign ingestion.
- OHM borders pipeline runs — orthogonal existing workflow.
- Confidence-scoring rework (P3) beyond what shipped — campaign relies on spot-checks + repair tooling instead of new scoring logic.
- Admin AI agent work — unrelated surface.
- Re-importing or repairing the June dataset — superseded by fresh start.
