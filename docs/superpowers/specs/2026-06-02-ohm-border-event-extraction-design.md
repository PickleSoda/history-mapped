# OHM Border Event Extraction Design

> **Date:** 2026-06-02
> **Status:** Approved
> **Related plans:** `2026-04-11-ohm-border-event-extraction-implementation.md`

## Problem

OHM border relations carry `start_event`, `end_event`, and `start_event:wikidata` / `end_event:wikidata` tags that describe the historical events causing territorial changes (e.g. "Treaty of Berlin", "Aster Revolution"). These events are currently lost during the border pipeline because only polity metadata and geometry periods are emitted. There is no durable artifact capturing event references, and no path to later import event entities from border-derived hints.

## Goal

Add a post-processing pipeline that reads existing `output/ohm_borders/<run_id>/parsed/*.jsonl` artifacts and extracts normalized start/end event references without re-querying OpenHistoricalMap. Enrich explicit or inferred Wikidata matches and emit durable event-reference artifacts.

## Architecture

Three-layer design:

1. **Event extractor** (`event_extractor.py`) — reads parsed border shards, scans root and stage tags for event references, emits normalized candidate records
2. **Event enricher** (`event_enricher.py`) — batches explicit QIDs through Wikidata SPARQL, falls back to exact-title search for missing QIDs, records match provenance
3. **Event stage orchestrator** (`stage_events.py` or inline in `stages.py`) — drives scan → enrich → build with resume/force semantics

The event pipeline is a **sibling** to the border pipeline, not a replacement. It consumes border artifacts and writes into a separate `events/` subtree under the same run directory.

## Artifact Layout

Under `output/ohm_borders/<run_id>/`:

```
events/
  candidates/
    event-candidates-00001.jsonl
  enriched/
    event-enriched-00001.json
  final/
    ohm_border_event_refs.jsonl
    ohm_border_event_matches.jsonl
```

Manifest shape:

```json
{
  "run_id": "run-001",
  "stages": {"fetch": {}, "parse": {}, "enrich": {}, "build": {}},
  "event_stages": {"scan": {}, "enrich": {}, "build": {}}
}
```

## Output Contracts

### `ohm_border_event_refs.jsonl`

Each line:

```json
{
  "event_role": "start",
  "event_label": "Treaty of Berlin",
  "resolved_wikidata_id": "Q1048169",
  "polity_ohm_relation_id": "28513",
  "stage_ohm_relation_id": "999",
  "polity_name": "Austria-Hungary",
  "event_date": "1908-10-06",
  "match_source": "explicit_qid",
  "match_confidence": "high",
  "source_tags": {
    "start_event": "Treaty of Berlin",
    "start_event:wikidata": "Q1048169"
  }
}
```

### `ohm_border_event_matches.jsonl`

Audit record per enrichment attempt:

```json
{
  "event_label": "Treaty of Berlin",
  "resolved_wikidata_id": "Q1048169",
  "match_source": "explicit_qid",
  "match_confidence": "high",
  "search_evidence": null
}
```

## Enrichment Policy

1. **Explicit QID preferred** — if `start_event:wikidata` or `end_event:wikidata` exists, use it directly
2. **Exact-title fallback** — if no QID, search Wikidata by exact English title; require unambiguous single-result match
3. **Unresolved** — if neither path yields a match, keep the label but set `resolved_wikidata_id` to null

Match sources:
- `explicit_qid`
- `exact_title_search`
- `unresolved`

## CLI Surface

```powershell
py -m pipeline borders events-scan --run-id run-001
py -m pipeline borders events-enrich --run-id run-001
py -m pipeline borders events-build --run-id run-001
py -m pipeline borders events-run --run-id run-001
```

Options:
- `--candidate-shard-size=500` (scan stage)
- `--event-enrich-batch-size=50` (enrich stage)
- `--event-enrich-workers=4` (enrich stage)
- `--resume`, `--force` (all stages)

## Non-Goals

- No event entity creation in the database
- No `geometry_periods.source_event_id` wiring
- No new Laravel schema migrations
- No attempt to reconstruct full event chronologies from border tags alone

## Testing Strategy

1. **Artifact path tests** — deterministic event directory and filename helpers
2. **Extractor tests** — root/stage tag extraction, duplicate handling, missing labels
3. **Enricher tests** — explicit QID path, exact-title fallback, ambiguous rejection
4. **Stage tests** — scan/enrich/build orchestration with resume/force
5. **CLI tests** — command registration and end-to-end `events-run`
6. **Manual smoke test** — run against a real border artifact directory and inspect final outputs

## Components

- `pipeline/ohm_borders/event_extractor.py`
- `pipeline/ohm_borders/event_enricher.py`
- `pipeline/ohm_borders/artifacts.py` (extend with event paths)
- `pipeline/ohm_borders/manifest.py` (extend with event stages)
- `pipeline/ohm_borders/stages.py` or `pipeline/ohm_borders/stage_events.py` (orchestration)
- `pipeline/ohm_borders/__main__.py` (CLI wiring)
- `pipeline/tests/test_ohm_borders_event_artifacts.py`
- `pipeline/tests/test_ohm_borders_event_extractor.py`
- `pipeline/tests/test_ohm_borders_event_enricher.py`
- `pipeline/tests/test_ohm_borders_event_stages.py`
- `pipeline/tests/test_ohm_borders_event_cli.py`

## Relationship to Existing Plan

This design formalizes the `2026-04-11-ohm-border-event-extraction-implementation.md` plan with current artifact conventions and updated module boundaries. The staged parallel border pipeline is already implemented; this is a consumer of its `parsed/` outputs.
