# Historical Entity Agentic Pipeline — Runbook

> **Status:** MVP — **15-node** LangGraph workflow with mocked-LLM test coverage
> **Date (this revision):** 2026-06-12
> **Package:** `pipeline/agent/`

> ⚠️ **Known critical issues (read before relying on this).** On a real (non-mocked) run the pipeline currently
> **persists nothing to the database while reporting success**: `commit_writer` writes JSONL to a host path the app
> container cannot see, never checks the artisan return code, and sends relations to the wrong importer with a directory
> argument; chronicles are written to disk but never imported. See [../plans/bug-report.md](../plans/bug-report.md)
> (PP-1…PP-7) and the improvement plan [../plans/agentic-pipeline-improvements.md](../plans/agentic-pipeline-improvements.md).
> The MVP is useful today as an **artifact generator** (the JSONL/manifest are correct); the DB-commit half is not yet working.

---

## What It Does

The agentic pipeline accepts raw historical text (video transcripts, articles, book excerpts) and produces structured, validated entity, relation, and **chronicle** proposals. It can auto-commit high-confidence items and flag the rest for human review.

**Example input:**

```text
In 1121, David IV of Georgia defeated Ilghazi at the Battle of Didgori.
```

**Pipeline steps (the compiled linear graph, `graph/workflow.py:48-63`):**

1. **Preprocess** — LLM clean-up/normalization of the raw transcript
2. **Parse** the text into structured events
3. **Extract** candidate entities and relations
4. **Lookup** existing DB entities (deduplication)
5. **Resolve Wikidata** IDs and metadata (Wikidata **REST** API, not SPARQL)
6. **Resolve OHM** geometry
7. **Generate** flowing summaries and relation descriptions
8. **Validate** against type policies and confidence thresholds
9. **Build diff** — sort into create / review / blocked buckets
10. **Approval gate** — auto-commit items above the per-type confidence threshold
11. **Commit** — write entity/relation JSONL and invoke Laravel artisan importers
12. **Resolve entity IDs** — map committed names back to DB ids for chronicle linking
13. **Build chronicle** — assemble the chronicle and its entries from committed items
14. **Write chronicle** — write `chronicle.json` (does **not** import it — see known issues)
15. **Audit** — write a manifest with the full decision trace

> The graph is strictly linear with no conditional edges, interrupts, or checkpointer. `messy_research` exists as an
> unregistered stub and is **not** in the graph; `style_validator`, the `wikipedia` tool, and `deepagents/` are present but
> unused. The `--no-create-chronicle` flag is plumbed into state but read by no node, so it currently has no effect.

---

## Quick Start

```powershell
py -m pipeline agent --input docs/example_transcript.txt --run-id demo_001
```

Output lands in `output/agent_runs/<run_id>/`:

```text
output/agent_runs/demo_001/
├── manifest.json              # Full audit trail
├── entities_to_create.jsonl   # Importer-ready entity records
├── relations_to_create.jsonl  # Importer-ready relation records
└── chronicle.json             # Chronicle + entries (written to disk only; not auto-imported)
```

---

## Commands

### Run the agent on a text file

```powershell
py -m pipeline agent --input transcript.txt --run-id my_run
```

Options:
- `--input PATH` — path to raw historical text (required)
- `--run-id TEXT` — deterministic ID for the artifact directory; defaults to `agent_<filename>`
- `--title TEXT` — optional chronicle title
- `--create-chronicle` / `--no-create-chronicle` — toggle chronicle building (⚠️ currently a no-op: the flag is stored in state but read by no node)

### Run the full test suite

```powershell
py -m pytest pipeline/agent/tests/ -v
```

The suite covers schemas (incl. chronicle), state, config, tools, the graph nodes, workflow compilation, and end-to-end
execution. Note the LLM and artisan calls are **mocked**, so the green suite does not exercise the live DB-commit path —
the known write-path defects are invisible to CI.

---

## Architecture

```text
Raw historical text
        ↓
┌─────────────────────────────────────────────────────────────┐
│  LangGraph Orchestrator  (pipeline/agent/graph/)            │
│  ─────────────────────  (strictly linear, no checkpointer)  │
│  preprocess_transcript → LLM: clean/normalize raw text      │
│  parse_sequence      → LLM: raw text → structured events    │
│  extract_candidates  → LLM: events → entities/relations     │
│  db_lookup           → Check existing PostgreSQL entities   │
│  resolve_wikidata    → Wikidata REST API: QIDs, metadata    │
│  resolve_ohm         → SQLite index: geometry resolution    │
│  generate_content    → LLM: summaries + descriptions        │
│  validate            → Policy: type checks, confidence      │
│  build_diff          → Sort into create/review/blocked      │
│  approval_gate       → Confidence-threshold auto-commit     │
│  commit_writer       → JSONL + artisan pipeline:import*     │
│  resolve_entity_ids  → Map committed names → DB ids         │
│  chronicle_builder   → Assemble chronicle + entries         │
│  chronicle_writer    → Write chronicle.json (no DB import)  │
│  audit_logger        → manifest.json with full trace        │
└─────────────────────────────────────────────────────────────┘
        ↓
  output/agent_runs/<run_id>/
  (* commit_writer's DB import does not currently succeed — see known issues)
```

### Tool Layer

Deterministic wrappers around existing pipeline modules:

| Tool | File | Wraps |
|------|------|-------|
| DB search | `tools/db.py` | `psycopg` direct queries (swallows errors → `[]`) |
| Wikidata | `tools/wikidata.py` | Wikidata **REST** action API (`wbsearchentities` + `Special:EntityData`), via `requests` — not SPARQL |
| Wikipedia | `tools/wikipedia.py` | Wikipedia REST API (**currently unused** by the graph) |
| OHM | `tools/ohm.py` | `xml_lookup.py`, `point_resolver.py` |
| App API | `tools/app_api.py` | `docker compose exec app php artisan …` (no return-code check, no timeout) |

---

## Node Reference

| # | Node | Type | Description |
|---|------|------|-------------|
| 1 | `preprocess_transcript` | LLM (via `create_llm()`) | Cleans/normalizes the raw transcript before parsing |
| 2 | `parse_sequence` | LLM (via `create_llm_with_fallbacks()`) | Converts raw text into `ParsedEvent[]` with labels, dates, and mentioned entities |
| 3 | `extract_candidates` | LLM (via `create_llm_with_fallbacks()`) | Extracts `CandidateEntity[]` and `CandidateRelation[]` from parsed events |
| 4 | `db_lookup` | Deterministic | Skipped under `--refresh`. Otherwise marks a candidate as existing only on an **exact case-insensitive name match of the same type** (the DB search is a substring `ILIKE`, so "Franks" must not match "Kingdom of the Franks"), else on its Wikidata QID; both are **date-guarded against namesakes** (see *Temporal namesake guard*); the matched row (`entity_id`, name, QID) is stored in `wikidata_match["existing_entity"]` and carried downstream |
| 5 | `resolve_wikidata` | Deterministic | Searches Wikidata via the **REST** action API and enriches candidates with QIDs, dates, coordinates |
| 6 | `resolve_ohm` | Deterministic | Searches the OHM SQLite index by QID or name; resolves best-point geometry |
| 7 | `generate_content` | LLM (via `create_llm_with_fallbacks()`) | Writes 1–2 sentence summaries and directional relation descriptions (note: `style_validator` is **not** invoked — no style enforcement) |
| 8 | `validate` | Deterministic | Checks entity/relation types against allow-lists; seeds confidence at a flat **0.95** + enrichment bonuses (see Risk Policies caveat) |
| 9 | `build_diff` | Deterministic | Sorts validated candidates into `create_entities`, `create_relations`, `review_items`, `blocked_items` |
| 10 | `approval_gate` | Deterministic | Auto-commits items at/above the per-type confidence threshold; flags everything else for review. Campaign handoffs commit Wikidata/geometry shortfalls as `needs_review`, and below-threshold relations at confidence `medium`, instead (see *Campaign approval-gate policy*). Any run commits a `db_lookup` namesake (`namesake_flag`) as `needs_review` with flag `namesake_ambiguous` |
| 11 | `commit_writer` | I/O | Writes `entities_to_create.jsonl`/`relations_to_create.jsonl`; invokes `pipeline:import` and `pipeline:import-borders` (⚠️ see known issues — these currently fail silently) |
| 12 | `resolve_entity_ids` | Deterministic | Maps labels → DB ids for chronicle linking: pre-seeded with `db_lookup`'s existing matches, then committed entities by QID (only when the QID row's name is compatible with the label — see *Endpoint resolution*) or exact name, both date-guarded by the record's `identity_span` (a same-name namesake of another era is never mapped); relation ids are looked up by endpoint entity ids first, then by labels |
| 13 | `chronicle_builder` | Deterministic | Assembles the `Chronicle` and its entries from committed items + resolved ids |
| 14 | `chronicle_writer` | I/O | Writes `chronicle.json` (⚠️ does **not** call `chronicles:import` — the chronicle never reaches the DB) |
| 15 | `audit_logger` | I/O | Writes `manifest.json` with run metadata, counts, audit log, and error list |

---

## Risk Policies

Each entity and relation type has a risk level and auto-commit threshold:

| Risk Level | Types (examples) | Threshold | Auto-commit? |
|------------|------------------|-----------|--------------|
| High | `person`, `political_entity`, `dynasty` | 0.97 | Only if confidence ≥ 0.97 |
| Medium | `city`, `archaeological_culture` | 0.94 | Only if confidence ≥ 0.94 |
| Low | `event_battle`, `event_war`, `trade_route` | 0.90 | Only if confidence ≥ 0.90 |

Configured in `pipeline/agent/config.py`. Relations have their own table (`RELATION_RISK_POLICIES`):
`rules`/`governed_by` 0.97 (high), `at_war_with` 0.95, `part_of`/`succeeded_by`/`preceded_by` 0.93, the
event-anchored ones 0.90, everything else the 0.95 default.

**Relation score.** A relation that passes validation scores `0.95`, plus `0.02`
(`validate.RELATION_CORROBORATION_BONUS`) when **both** ends carry a Wikidata QID (the resolved match, or
the existing DB row's `wikidata_id`). An invalid one scores `0.3` and is blocked. So the high-risk
predicates `rules`/`governed_by` (0.97) auto-commit only between two Wikidata-identified ends, the same
way the high-risk entity types need a Wikidata bonus. Before 2026-10-05 the score was a flat 0.95, so these
two predicates could never auto-commit and were held on every run.

> ⚠️ **Caveat — the gate is currently a near-rubber-stamp.** `validate.py` seeds entity confidence at a flat `0.95`
> plus enrichment bonuses (Wikidata/OHM only *add*), so a validated entity with zero external corroboration already sits
> at 0.95. The five low-risk types and every valid relation except `rules`/`governed_by` therefore auto-commit
> unconditionally; only `person`/`political_entity`/`dynasty` (0.97) and those two predicates need a bonus. Confidence is decoupled from evidence quality, and the
> `requires_wikidata` blocking penalty is dead code (no policy sets it). See PP-5 in the bug report and the evidence-based
> rescoring item in the improvement plan.

### Campaign approval-gate policy

Campaign handoffs are authored from wiki sources and pass review before they are ingested, so the
gate does not hold their entities for a weak external match. A run counts as a campaign handoff
when **both** `summaries_precomputed` is true **and** its run id starts with `campaign_`
(`pipeline.campaign.paths.RUN_PREFIX`). Either signal alone is not enough: any offline handoff
sets `summaries_precomputed`, and `--run-id campaign_x` can be given to a full-LLM run.

In a campaign run, an entity under its type threshold is **committed** with
`verification_status = needs_review` (not `pipeline_draft`) when its shortfall comes from:

| Flag (`attributes.validation_flags`) | Cause |
|---|---|
| `no_wikidata_match` | `resolve_wikidata` found no match |
| `low_wikidata_match` | a match whose corroboration bonus alone does not clear the threshold (`0.95 + system_confidence < threshold`) |
| `missing_geometry` | a geo-sensitive type (`validate.GEO_SENSITIVE_TYPES`) with no geometry |

These are the only confidence penalties `validate` applies, so an entity that falls short for any
other reason is still held in `review_items.jsonl`. Committing the entity means the run's
relations and chronicle entries that name it resolve instead of dangling. The entity stays
flagged for later work: list it with `?status=needs_review` (API or admin filter), then QID-match
it (`pipeline.reresolve_entities <name>`) or review it by hand. A later `--refresh` ingest that
does resolve it imports it as `pipeline_draft` again. Its old `validation_flags` stay in `attributes`,
so go by the status, not the flags. Non-campaign runs keep the plain gate.

`ImportEntityJob` honours only `needs_review` from a record; every other value, including a
missing one, becomes `pipeline_draft`, so an import can never promote a row.

**Relations.** The campaign reviewer audits every relation's type and direction. So, in a campaign
run, a relation that passed validation and is held **only** because its score is below its
predicate threshold is **committed** at `relationships.confidence = medium`
(`approval_gate.REVIEWED_RELATION_CONFIDENCE`: it passed review but not the auto-threshold) instead of
being held. In practice this means `rules`/`governed_by` between ends that are not both on Wikidata. The
gate sets `CandidateRelation.commit_confidence`, and resets any other value, so a handoff cannot set it.
`commit_writer` writes it to the `relations.jsonl` line as `"confidence": "medium"` and adds
`"approval": "campaign_review"` to `source_citations`. `pipeline:import-relations` stores the
confidence. A relation that clears its threshold carries neither key, so the importer default
(`medium`) applies. To find the review-committed rows, use `source_citations->>'approval'`, not
`confidence`. Non-campaign runs keep holding them in `review_items.jsonl`.

**2026-10-05 recovery.** Before this policy, every campaign run held all of its valid
`rules`/`governed_by` relations. They were recovered in one insert-only pass. Wave 2 runs listed
them in `review_items.jsonl`. Wave 0+1 runs never wrote that file, so their relations were
rebuilt from each reviewed run's `candidates.json`, with the same validity checks as `validate`.
The records were built by `commit_writer._relation_to_jsonl_record`, with endpoint ids taken from
the run's own `relations.jsonl` and `entities_to_create.jsonl`. They were imported with
`pipeline:import-relations` in its default identity-first mode, without `--force`, so existing
triples were skipped. The rows carry `created_by = pipeline:held-relations-recovery-20261005` and
`source_citations.recovered_from` (`review_items` | `reconstructed`). The files are in
`api/storage/app/pipeline/held-relations-20261005/`, and the pre-import dump is
`output/campaign-backups/db-pre-held-relations-20261005.sql.gz`. The pass created 4,639 rows: 3,184
from `review_items` and 1,455 reconstructed. It skipped 631 records whose triple already existed, and
57 records stayed unresolved (31 names: a QID whose row has a different name, or a QID or name not in
the DB). Two known defects were left in place, because the pass was insert-only:
`dateless-first-followup.tsv` lists 34 triples where a dateless copy was imported first and a dated copy
was then skipped. `outside-ruler-lifespan.tsv` lists 183 of the 2,999 checkable rows (93 of them more
than 50 years off) whose span lies outside the ruler's life. Most of these are namesake mislinks
inherited from the run's own entity matching, for example the Macedon "Philip II" row used for Spain in
1556, or Charles V of France used for the HRE in 1519. Live campaign runs link `rules` the same way, so
bare regnal names remain a risk.

**Transient Wikidata errors.** Retries happen only at the HTTP layer:
`tools/wikidata._get_honoring_retry_after` retries 429/503 up to 3 times, honouring
`Retry-After`. There is no per-entity retry. A lookup that still fails (throttling that outlasts
the retries, or a network error/timeout, which is not retried) returns no candidates, which looks
the same as a genuine miss. In a campaign run that entity is therefore committed as
`needs_review` with `no_wikidata_match`, and the same QID-match pass picks it up.

---

## Output Artifacts

### `manifest.json`

```json
{
  "run_id": "demo_001",
  "timestamp": "2026-06-10T14:32:00+00:00",
  "input_preview": "In 1121, David IV defeated...",
  "parsed_events_count": 1,
  "candidate_entities_count": 4,
  "candidate_relations_count": 2,
  "enriched_entities_count": 4,
  "validation_results_count": 6,
  "committed_count": 1,
  "errors_count": 0,
  "audit_log": [...],
  "errors": []
}
```

### `entities_to_create.jsonl`

```json
{"name": "David IV of Georgia", "entity_type": "person", "summary": "Ruled the Kingdom of Georgia from 1089 to 1125...", "wikidata_id": "Q405", "temporal_start": null, "temporal_end": null, "alternative_names": ["David IV"], "geojson": null, "source_citations": {"created_by": "historical-agent-pipeline", "confidence": 0.98}}
```

> The entity JSONL keys are `temporal_start`/`temporal_end` and `geojson` (not `start_date`/`end_date`/`geometry`),
> matching what `pipeline:import` expects.

### `relations.jsonl`

```json
{"source_name": "David IV of Georgia", "source_wikidata_id": "Q405", "target_name": "Battle of Didgori", "target_entity_id": "6f1c…", "relationship_type": "participated_in", "start_date": "1121-08-12", "end_date": "1121-08-12", "description": "Commanded the Georgian forces at the Battle of Didgori on August 12, 1121.", "source_citations": {"created_by": "historical-agent-pipeline"}}
```

Each end carries its name plus, when known, its identity: `<side>_entity_id` (a `db_lookup`
existing match) and `<side>_wikidata_id` (the QID the entity is imported with). Entities held
by the approval gate get no ids (their QID was never vetted). All id fields are optional, so
older files without them still import. A campaign relation committed below its threshold also
carries `"confidence": "medium"` and `source_citations.approval = "campaign_review"`. See
*Campaign approval-gate policy*.

### `review_items.jsonl`

Everything the approval gate held back (`{"type": "entity", "label": …, "reason": "confidence
0.90 < threshold 0.94"}`), written only when non-empty. Held entities are **not** imported, so
relations and chronicle refs that name them stay unresolved; this file is the per-run list to
review. In campaign runs, Wikidata/geometry shortfalls are committed as `needs_review`, and
below-threshold relations are committed at `medium`, rather than listed here (see *Campaign approval-gate policy*). Their `entities_to_create.jsonl` lines carry
`"verification_status": "needs_review"` and `"validation_flags": [...]`.

### Endpoint resolution (relations and chronicle secondary entities)

`pipeline:import-relations` and `chronicles:import` share `App\Services\EntityReferenceResolver`,
which resolves each reference identity-first:

1. `entity_id`: an existing DB row (uuid)
2. `wikidata_id`: the QID row, accepted only if its name or one of its aliases is
   *name-compatible* with the label. After normalising, one name must be a whole-word run
   inside the other, and their regnal/ordinal markers (roman numerals, digits, ordinal words)
   must be equal. Pipeline QIDs are sometimes wrong ("World War I" carried World War II's QID,
   "Malik-Shah" was given Malik-Shah II's, "Qi" got Qing dynasty's), and the entity import
   merges by QID, so an unguarded QID hit would attach facts to the wrong entity.
3. exact name
4. case-insensitive name
5. alternative name (`entity_aliases`), only when it names exactly one entity

Steps 2-5 are also **date-guarded** when the caller passes a reference span (the relation's
dates for contemporaneous types, the chronicle entry's years): see *Temporal namesake guard*
below. Step 1 is an identity assertion and is not date-checked.

A record whose two ends land on the same row is skipped (`self_loops`). The importer prints
`RELATION_IMPORT_SUMMARY` (adding `unresolved_names`, `resolved_via` and `self_loops`) and a
compact `RELATION_UNRESOLVED ["<name> (<reason>)", …]` list. `chronicles:import` prints
`CHRONICLE_UNRESOLVED`. The Python mirror of the name guard is
`pipeline/agent/tools/disambiguation.py:names_compatible`; keep the two in sync.

**Identity guard at resolution and import (2026-10-04).** The same check now stops wrong QIDs
at the source. Before, a wrong QID made `pipeline:import --force` overwrite another entity's row.
In the 2026-10-03 wave about 25% of the endpoints merged by QID into a differently named row were
wrong (`output/campaign/audit/qid-corruption-20261004.csv`).

- **Shared rules** in `pipeline/agent/tools/disambiguation.py`. PHP mirrors them in
  `EntityReferenceResolver::namesConflict` / `recordMatchesRow`; keep the two in sync.
  - `names_conflict(a, b)` reports a positive disagreement:
    - `markers`: both names carry regnal or ordinal markers and they differ (World War I/II,
      Mithridates VI/V, Eighteenth/Nineteenth Dynasty).
    - `near_miss`: a token is a non-inflectional extension of the other's (Qi/Qing,
      Julian/Juliana, Gaza/Gazala) or a near-spelling at ≥ 0.7 Levenshtein similarity
      (Romagna/Romania). Plurals and demonyms (Ottomans, Assyrian, Frankish) are not conflicts.
  - Normalisation drops apostrophes and ayn/hamza marks and transliterates letters that NFKD
    cannot decompose (đ, ø, ł, ß …).
- **`resolve_wikidata`** passes the reranked candidates through `screen_candidates` before it
  picks one, so a correct namesake further down the list can still win. A candidate is dropped
  when:
  - its P31 is in `UNIVERSAL_BLOCK_P31` (disambiguation page, given or family name, taxon);
  - none of its names (search label/aliases, `wbgetentities` English aliases, now fetched in
    `fetch_entity_meta`) is `names_compatible` with the item's label or aliases. The exception
    is an exact full-name search hit (`match_text`, e.g. "Coptos" for Qift) whose labels do not
    differ on a marker;
  - its label differs from the item's and, for lifetime-bounded kinds, its Wikidata dates lie
    more than 400 years from the item's own dates (600 when only the transcript era is known).
    For example, "Julian" (c. 360) must not resolve to Julian of Norwich. The distance is
    BCE/CE-sign-insensitive.

  A pre-assigned QID gets the same name check. When it fails, the node logs `REJECTED (name
  guard …)` and re-searches. `reresolve_entities.py` and `repair_committed_data.py` use the same
  screen. `db_lookup` name-guards its QID lookup.
- **OHM** (`ohm_polity_resolver.relevance`). Era may still carry a foreign canonical name such
  as Imperium Romanum Orientale. A feature now scores 0 when:
  - its name differs from the query on a regnal/ordinal marker; or
  - its `wikidata` tag differs from the entity's own QID and the names are not compatible.
    Example: Romania (Q218) had taken the 1861-69 Romagne feature (Q244482), and the shared
    OHM id then merged Romagna into the Romania row. Near-misses are *not* vetoed here, because
    OHM's canonical is often the right answer spelled in another language (Romagne for Romagna).
- **Import** (`ImportEntityJob::findExisting`, and `ImportEntitiesCommand::isDuplicate` without
  `--force`). A row found by QID or OHM id is merged into only when
  `recordMatchesRow(name, alternative_names, [row name, …row aliases])` holds:
  - the record's name is compatible with the row's name or an alias; or
  - one of its alternative names is, and its name does not *conflict* with the row's name.

  The OHM canonical alias, taken from the manifest's display name, is excluded from the evidence
  because it comes from the match being checked. When a QID match is rejected, the record
  imports as its own entity (or falls through to the OHM-id and name+era checks) with
  `wikidata_id = NULL`, keeps `attributes._rejected_wikidata_id`, and logs
  `[Pipeline] Identity guard: …`.

Repairing the rows the 2026-10-03 batch already corrupted is a separate, unapplied plan:
`output/campaign/audit/qid-repair-plan.md`.

**Temporal namesake guard (2026-10-05).** The name guard cannot tell namesakes apart: bare
regnal labels ("Philip II", "Charles V", "al-Mustansir") are the *same* name for different
people, so the Macedonian Philip II came to rule Spain in 1556 and Charles V of France the Holy
Roman Empire in 1519 (183 of 2,999 checkable recovered `rules` relations fell outside the
ruler's lifespan: `api/storage/app/pipeline/held-relations-20261005/outside-ruler-lifespan.tsv`).
Dates can tell them apart, in all three layers.

- **Shared rule** in `pipeline/agent/tools/disambiguation.py` (`temporal_fit`, `pick_namesake`),
  mirrored by `EntityReferenceResolver::temporalFit` / `pickNamesake` (keep in sync). Two year
  spans of one entity type are:
  - `match` when they overlap;
  - `near` when the gap is within the type's tolerance (the same person with slightly
    different dates: a reign vs a lifespan, two chronologies);
  - `conflict` beyond it (a namesake);
  - `unknown` when a side is undated or the type is not date-checked.

  Tolerances (`NAMESAKE_TOLERANCE_YEARS`): person 60, dynasty 150, military unit 100,
  `event_*` 50, migration and epidemic 100, each +75 when either span reaches before 1000 BCE
  (Mesopotamian middle/short chronologies differ by ~60 years). Polities, places and cultural
  types are **never** date-checked: their spans are fuzzy or open-ended, and one generic row
  (Egypt) serves many eras. Like `era_distance`, the gap is BCE/CE-sign-insensitive
  ("Augustus rules Gallia 27" means 27 BCE). A single bound is a point, except that a lone
  round-century year (`-800`, `100`) counts as ±100. Such a year is usually a Wikidata
  century-precision date stored as one year (Catualda, c. 19 CE, is stored as "100").
- **Choosing among same-name rows** (`pick_namesake`): `conflict` rows are dropped and the best
  non-empty tier wins (`match` > `near` > `unknown`). There is no answer (`namesake_ambiguous`)
  when every row conflicts, or when the best tier holds rows that conflict *with each other*
  (two dated namesakes and no date to choose by). Rows that are undated or mutually compatible
  are presumed duplicates of one entity, and the oldest wins, as before.
- **Pipeline** (`db_lookup`). The reference span is the candidate's own dates. Failing that
  (a third of campaign persons are undated), it is the union of the dates of the run's
  contemporaneous relations naming the candidate, and failing that, its `source_event`'s dates.
  The span is stored as `identity_span`. The name match and the name-guarded QID match are both
  date-guarded; a compatible QID row settles an ambiguous name. When nothing qualifies, the
  candidate is **not** existing, gets `namesake_flag = "namesake_ambiguous"`, and is created as
  a new entity. `approval_gate` commits it as `needs_review` with that validation flag in every
  run. `commit_writer` writes `_identity_span` into an undated record and `identity_span` into
  the committed change. `resolve_entity_ids` uses it for its QID and name lookups.
  `search_entity_by_name` / `_by_wikidata_id` now return `start_year` / `end_year` from the
  primary `entity_temporal_ranges` row and list exact name matches first.
- **Import** (`ImportEntityJob::findExisting`, which `ImportEntitiesCommand::isDuplicate` now
  calls so the pre-import dedup applies the same rules). The record's span is its
  `temporal_start`/`temporal_end`, else `_identity_span`.
  - A QID or OHM row of another era is never merged into. The QID is dropped to
    `attributes._rejected_wikidata_id`, and the log reads `[Pipeline] Namesake guard: …`.
  - For date-checked types, the name+type path uses `pick_namesake`, so a `near` row still
    merges.
  - Other types keep the strict era-overlap test.
  - A new row created because of a namesake gets `needs_review` and the flag
    `namesake_ambiguous`.
- **Relations and chronicles** (`EntityReferenceResolver::resolve(..., $span)`).
  - `pipeline:import-relations` passes the relation's dates only for
    `CONTEMPORANEOUS_RELATION_TYPES` (`rules`, `succeeded_by`, `fought_at`, `married_to`,
    `signed_by`, … — types implying the person was alive). `influenced_by`, `inspired`,
    `caused`, `spread_to` etc. may name the long dead and are not checked.
  - `chronicles:import` passes the entry's years.
  - A QID row of another era falls through to the name lookup. Same-name rows are chosen by
    date; when every one is of another era, a unique compatible alias row may still match.
  - Otherwise the end stays unresolved with the reason `namesake_ambiguous: …`, listed in
    `RELATION_UNRESOLVED` / `CHRONICLE_UNRESOLVED`.
- **Trade-off.** A row whose own dates are wrong (the caliph "Abu Bakr" carrying al-Razi's
  866-925) now refuses its correct links instead of accepting them. On 2026-10-05 data, about
  1,150 of ~35k date-checkable relation ends (905 of them person ends) lay beyond tolerance.
  Fix the row's dates rather than loosening the guard. The repair plan for the namesake links
  already in the DB is `output/campaign/audit/namesake-repair-plan.md` (unapplied). At the
  source, `handoff check` warns `ambiguous-label` on bare regnal person labels (see *Campaign
  tooling*).

**Re-running old artifacts (additive repair).** Both commands can be re-run over existing run
directories without duplicating anything:

```bash
C=/var/www/html/storage/app/pipeline/agent_runs; R=<run_id>
php artisan pipeline:import-relations $C/$R/relations.jsonl \
    --entities-file=$C/$R/entities_to_create.jsonl --additive-recovery --batch-id=recovery-<date>:$R
php artisan chronicles:import $C/$R/chronicle.json --link-missing
```

`--entities-file` backfills each end's QID by name for legacy files. `--additive-recovery`
resolves names first (the legacy behaviour) and uses ids only where the name finds nothing, so a
record the old import already linked is never re-pointed and no parallel copy is added. Existing
`(source, target, type)` rows are skipped. `--link-missing` only attaches secondary entities
missing from existing entries (matched by identical `narrative_text`). It never creates or
deletes chronicles, entries or links, never touches chronicle metadata, and refuses `--force`.

---

## Environment Variables

Add to `pipeline/.env`:

```dotenv
# OpenAI (default)
OPENAI_API_KEY=sk-...

# Or OpenRouter / any OpenAI-compatible provider
LLM_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-v1-...
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | API key for the LLM provider |
| `LLM_BASE_URL` | No | OpenAI default | Custom base URL for OpenAI-compatible endpoints |

### Provider examples

**OpenRouter** — access 100+ models through a single endpoint:
```dotenv
LLM_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-v1-...
```
Then override model names in `pipeline/agent/config.py`:
```python
parse_model: str = "anthropic/claude-3.5-sonnet"
extract_model: str = "anthropic/claude-3.5-sonnet"
generate_model: str = "anthropic/claude-3-opus"
```

**Ollama (local)**:
```dotenv
LLM_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama  # Ollama ignores this, but LangChain requires a non-empty string
```
```python
parse_model: str = "llama3.1"
extract_model: str = "llama3.1"
generate_model: str = "llama3.1"
```

**vLLM / LM Studio / other local servers**:
```dotenv
LLM_BASE_URL=http://localhost:8000/v1
OPENAI_API_KEY=not-needed
```

The LLM layer is provider-agnostic via `pipeline/agent/llm.py:create_llm()`, which wraps `langchain_openai.ChatOpenAI` with configurable `base_url`, `model`, and `api_key`.

## Handoff Mode (--from-candidates)

For campaign-scale generation, an opencode session performs the LLM stages offline (parse, extract, completeness-critic recall loop, summaries per `style_guide.md`) and writes a handoff file; the graph then runs its deterministic tail (db_lookup → … → audit_logger) with **zero LLM calls**.

```bash
# 1. Author output/campaign/extractions/<run_id>/candidates.json
#    (schema contract: docs/superpowers/specs/2026-08-23-history-data-campaign-design.md §4.1)
# 2. Validate the gate:
pipeline/.venv/bin/python -m pipeline.agent.validate_handoff output/campaign/extractions/<run_id>/candidates.json
# 3. Run the deterministic tail:
pipeline/.venv/bin/python -m pipeline agent --from-candidates \
  output/campaign/extractions/<run_id>/candidates.json --run-id <run_id>
# Batch: bash run_campaign.sh   (processes every pending extraction sequentially)
```

Events may carry a campaign-only `"fact": N` (the transcript fact number), which the slice commands use as the transcript-to-handoff join key. `ParsedEvent` ignores unknown keys, so the validator and the graph never see it.

Handoff binding rules: items match `ParsedEvent`/`CandidateEntity`/`CandidateRelation` pydantic schemas; `relationship_type` ∈ `validate.ALLOWED_RELATION_TYPES`; relation endpoints must all be extracted entities; when `summaries_precomputed` is true a top-level `"summaries"` map keyed by entity label supplies `summary`+`significance` for every candidate (generate_content skips its LLM entirely). Idempotency matches `run_agent()`: a clean manifest short-circuits re-runs (`--refresh` overrides). See the campaign design spec and `docs/superpowers/plans/2026-08-23-history-data-campaign.md` for the full workflow and measured pilot results.

### Campaign tooling

`pipeline/.venv/bin/python -m pipeline.campaign <command>`, run from the repo root, is the agent-facing CLI for authoring and operating the campaign. Every `RUN` accepts `campaign_<slug>` or the bare slug. Agent roles and the review loop are described in [campaign-orchestration.md](campaign-orchestration.md).

Run pytest and any heavy python through the memory-capped wrapper, with a wall-clock limit, one suite per process: `timeout 300 scripts/capped.sh pipeline/.venv/bin/python -m pytest pipeline/campaign/ -q`. The wrapper uses a systemd scope with `MemoryMax=3G` and no swap (override with `MEM_MAX`, at most 4G), so a runaway process is killed on its own and doesn't take the session down with it.

| Command | Purpose |
|---------|---------|
| `types [--relations-help]` | Allowed entity types (by group) and relation types, read from code; `--relations-help` adds source → target hints from `docs/entity-model/relationships.md` |
| `wiki TITLE... [--dated] [--max-chars 6000] [--section NAME]`, `wiki-search QUERY [--limit 5]` | en.wikipedia plain-text extracts / search, cached in `output/campaign/cache/wiki/`, throttled to ≤1 req/s |
| `transcript-check RUN` | Transcript lint: errors (exit 1) for facts with no explicit BCE/CE year or repeated numbers; warnings for numbering gaps, fewer than 60 or more than 120 facts, a first year outside the era's hard bounds (`out-of-era`) or span (`era-edge`), and out-of-order facts. Year detection is heuristic, so era and order findings are prompts to verify, never grounds to move a date |
| `handoff init RUN --title T [--force]` | Empty `candidates.json` skeleton; `--force` first moves the old file to `candidates.prev.json` |
| `handoff add RUN {events,entities,relations,summaries} FILE\|-` | Upsert a JSON array, validated per item against the pipeline models + type lists. Keys: label; relations `SOURCE\|TYPE\|TARGET`. Updates merge the given fields (`--replace` swaps the whole item). Valid items are written, rejects are itemised, exit 1 |
| `handoff rm RUN {events,entities,relations} KEY...` | Removing an entity cascades to its relations + summary; removing an event clears `source_event` references |
| `handoff slice RUN --facts 21-40` | One extraction slice without reading the whole transcript or handoff. Prints those numbered facts verbatim, the events already tagged with them, and every existing entity label grouped by type |
| `handoff rm-slice RUN --facts 21-40` | Undoes a slice's extraction so it can be redone without duplicates. Removes the events tagged with those facts and the relations whose `source_event` is one of them. Entities first mentioned there are removed unless another fact still uses them; those keep a repointed `source_event` |
| `handoff rename RUN OLD NEW [--merge]`, `handoff rename-event RUN OLD NEW [--merge]` | Relabel everywhere (relation endpoints, summaries, `mentioned_entities` / `source_event`); `--merge` folds OLD into an existing NEW |
| `handoff show RUN [--part P] [--labels-only]`, `handoff get RUN PART KEY...` | One line per item / full stored JSON of specific items |
| `handoff check RUN [--all] [--facts A-B]` | Fast lint. Errors exit 1 (dangling endpoints, bad types/dates, era bounds, missing summaries, duplicate labels). Warnings exit 0: orphans (tagged `(fact N)`), r/e < 1.3, near-duplicate labels, unknown `source_event`, `mention-missing` (a `mentioned_entities` label that isn't an entity), `ambiguous-label` (a person labelled with a bare regnal name such as "Philip II" or "al-Mustansir" instead of its English Wikipedia title; `pipeline/campaign/labels.py`, and `handoff add` prints it as a hint), event coverage, and the fact-tag checks `fact-missing` / `fact-uncovered` / `fact-range`. `--facts` lints only what that slice owns (its events, the entities first mentioned there, and relations whose `source_event` is one of its events) and adds `slice-density` (relations/fact ≥ 2, relations/new entity ≥ 1.5) |
| `handoff finalize RUN [--critic-iterations 2]` | Stamps `self_audit`, then runs `validate_handoff`; exit code mirrors the gate |
| `status [--era eNN] [--thin] [--validate] [--json]` | One row per run (facts, events, entities, relations, r/e, latest review verdict, ingest `clean`/`failed`/`-`) plus an era × region grid; lists handoffs edited after a clean ingest |
| `validate-all [--era eNN]` | Gate every handoff, print failures only |
| `review-record RUN --verdict {PASS,FIXED,REGATHER,ESCALATE} --model M [--issue T]... [--fixed T]...` | Append to the run's `review.json` history |
| `measure` | Spec §7 acceptance metrics via `docker compose ... exec -T db psql`; exit 2 if the DB is not running |

`bash run_campaign.sh` environment:

| Variable | Effect |
|----------|--------|
| `ONLY=<regex>` | Only run ids matching the bash ERE, e.g. `ONLY='^campaign_e0[45]__'` |
| `RETRY_FAILED=1` | Add `--refresh` for runs whose manifest recorded errors |
| `RUN_TIMEOUT=1800` | Per-run limit in seconds; a run that hits it is recorded as `TIMEOUT` |
| `EXTRA_AGENT_FLAGS` | Extra flags for every run (e.g. `--refresh`) |
| `DRY_RUN=1` | List what would run, without Docker |
| `SKIP_PREFLIGHT=1` | Skip the check that the compose `app` and `db` services are running (by default the driver exits 2 when either is down) |
| `CAMPAIGN_LOG_DIR` | Defaults to `output/campaign/logs/<YYYYmmdd-HHMMSS>/`, which holds one `<run_id>.log` per run plus `summary.txt` |
| `CAMPAIGN_SUMMARY`, `EXTRACTIONS_DIR` | Override the summary path / handoff root |

Each run is recorded in the summary as `ok`, `ERR rc=N`, `INVALID handoff`, `TIMEOUT` or `skip (clean manifest)`. The driver exits non-zero if any run failed.

Manifest behaviour: `run_agent_from_candidates` short-circuits only when `<AgentConfig.output_dir>/<run_id>/manifest.json` exists with `errors_count == 0`. A manifest with errors does **not** block a re-run: the run simply executes again in normal (non-refresh) mode. The driver skips clean manifests itself unless `--refresh` is in the flags. `RETRY_FAILED=1` adds `--refresh` to errored runs, so rows left by the partial first attempt are re-resolved and updated in place. A handoff edited after a clean ingest is never re-ingested automatically. `status` lists such runs as stale; re-ingest them with `ONLY=<run_id> EXTRA_AGENT_FLAGS=--refresh bash run_campaign.sh`.

**When `--refresh` is used.** `--refresh` becomes `--force` downstream: it skips the `db_lookup` existing-entity check (so every entity is re-resolved against Wikidata) and makes `ImportEntityJob` overwrite existing rows. A first-time ingest therefore must NOT use it: existing DB entities are kept as they are (first writer wins, their summaries are never redone), Wikidata resolution is skipped for them, and the run's relations and chronicle still link to them by the matched row's `entity_id` (carried in `relations.jsonl` and pre-seeded into `entity_id_map`; see *Endpoint resolution*). `scripts/campaign_ingest_loop.sh` passes `--refresh` only for runs whose manifest is already clean (stale handoff/review or `INGEST_REFRESH_BEFORE`), in a separate driver pass; runs with no manifest or an errored manifest run without it.

---

### Model Fallback Chains

Each LLM node has a primary model and an ordered fallback chain. If the primary model fails (rate limit, timeout, 5xx, etc.), the pipeline automatically retries and then falls back to the next model in the chain.

**Default fallback chains** (configured in `pipeline/agent/config.py`):

| Node | Primary | Fallback 1 | Fallback 2 | Fallback 3 |
|------|---------|------------|------------|------------|
| `parse_sequence` | `gpt-4o-mini` | `openai/gpt-oss-20b:free` | `google/gemma-4-26b-a4b-it:free` | `deepseek/deepseek-v3.1-terminus` |
| `extract_candidates` | `gpt-4o-mini` | `google/gemma-4-31b-it:free` | `openai/gpt-oss-120b:free` | `deepseek/deepseek-v3.1-terminus` |
| `generate_content` | `gpt-4o` | `deepseek/deepseek-v3.1-terminus` | `google/gemini-2.5-flash` | `x-ai/grok-4.20` |

Customize by editing `MODEL_FALLBACKS` in `pipeline/agent/config.py`:

```python
MODEL_FALLBACKS: dict[str, list[str]] = {
    "parse_model": [
        "openai/gpt-oss-20b:free",
        "google/gemma-4-26b-a4b-it:free",
        "deepseek/deepseek-v3.1-terminus",
    ],
    "extract_model": [...],
    "generate_model": [...],
}
```

To disable fallbacks, pass an empty dict or set `model_fallbacks={}` when constructing `AgentConfig`.

---

## Testing

```powershell
# All agent tests
py -m pytest pipeline/agent/tests/ -v

# Specific test files
py -m pytest pipeline/agent/tests/test_graph.py -v
py -m pytest pipeline/agent/tests/test_nodes_llm.py -v
py -m pytest pipeline/agent/tests/test_nodes_lookup.py -v
py -m pytest pipeline/agent/tests/test_nodes_proposal.py -v
py -m pytest pipeline/agent/tests/test_nodes_io.py -v
py -m pytest pipeline/agent/tests/test_tools.py -v
```

---

## LangGraph Development UI

For local development with a visual graph, node-execution tracing, and hot reloading, run the
graph under the LangGraph CLI and attach LangSmith Studio.

```powershell
# Install the in-memory dev server (requires Python 3.11+)
py -m pip install "langgraph-cli[inmem]"   # or: uv pip install "langgraph-cli[inmem]"

# Start the local server (hot reload, no Docker)
langgraph dev                              # serves http://localhost:2024

# On Python 3.10, run the server in a container instead:
langgraph dev --wait                       # requires Docker Desktop
```

Open Studio against the local server:

```
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

Studio gives you the workflow graph with per-node execution tracing, real-time state inspection,
and hot reload on code changes — all backed by local state storage.

---

## Module Layout

```text
pipeline/agent/
├── __init__.py
├── __main__.py              # CLI: py -m pipeline agent --input …
├── config.py                # AgentConfig + risk policies
├── llm.py                   # Provider-agnostic LLM factory (OpenAI, OpenRouter, Ollama, etc.)
├── style_guide.md           # Content generation prose rules
├── graph/
│   ├── __init__.py
│   ├── state.py             # AgentRunState TypedDict
│   ├── workflow.py          # StateGraph builder + run_agent()
│   └── nodes/
│       ├── preprocess_transcript.py  # node 1 (LLM clean-up)
│       ├── parse_sequence.py
│       ├── extract_candidates.py
│       ├── db_lookup.py
│       ├── resolve_wikidata.py
│       ├── resolve_ohm.py
│       ├── generate_content.py
│       ├── validate.py
│       ├── build_diff.py
│       ├── approval_gate.py
│       ├── commit_writer.py
│       ├── resolve_entity_ids.py     # maps committed names → DB ids
│       ├── chronicle_builder.py
│       ├── chronicle_writer.py
│       ├── audit_logger.py
│       └── messy_research.py    # Stub — NOT registered in the graph
├── style_validator.py       # Present but NOT invoked by any node
├── tools/
│   ├── db.py                # PostgreSQL search wrapper (errors → [])
│   ├── wikidata.py          # Wikidata REST action API search/enrich (not SPARQL)
│   ├── wikipedia.py         # Wikipedia API summary (unused by the graph)
│   ├── ohm.py               # OHM SQLite + geometry
│   └── app_api.py           # Laravel artisan shell-out
├── schemas/
│   ├── entities.py          # ParsedEvent, CandidateEntity, EnrichedCandidate
│   ├── relations.py         # CandidateRelation, CommittedChange
│   ├── proposals.py         # ProposedDiff, ApprovalDecision
│   ├── validation.py        # ValidationResult, PipelineError, AuditEvent
│   └── chronicle.py         # Chronicle, ChronicleEntry, ChronicleEntryEntity
├── deepagents/
│   └── __init__.py          # package only — the referenced agent stub files do NOT exist
└── tests/
    ├── test_schemas.py
    ├── test_state.py
    ├── test_config.py
    ├── test_llm.py           # LLM factory + fallback chain tests
    ├── test_tools.py
    ├── test_nodes_llm.py
    ├── test_nodes_lookup.py
    ├── test_nodes_proposal.py
    ├── test_nodes_io.py
    └── test_graph.py
```

---

## Design Documents

- **Design spec:** [`docs/archive/superpowers-specs/2026-06-09-historical-entity-agentic-pipeline-design.md`](../archive/superpowers-specs/2026-06-09-historical-entity-agentic-pipeline-design.md)
- **Implementation plan:** [`docs/archive/superpowers-plans/2026-06-09-historical-entity-agentic-pipeline.md`](../archive/superpowers-plans/2026-06-09-historical-entity-agentic-pipeline.md)
