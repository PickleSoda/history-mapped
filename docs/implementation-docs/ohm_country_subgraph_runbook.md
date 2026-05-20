# OHM Country Subgraph Runbook

This runbook describes the operator workflow for extracting one country-centered OHM border graph from an existing global OHM dump, then running the normal OHM parse, enrich, build, and relation stages on that subset.

Use this flow when you want a repeatable "country module" run such as the Roman Empire without re-fetching the full global Overpass dataset.

Seed resolution rules for the command:

- prefer `--seed-qid` when you know the polity's Wikidata ID
- use `--seed-name` only as an exact-name fallback
- if exact-name fallback matches zero or multiple candidates, stop and resolve the seed explicitly before continuing

## Inputs

- Existing global OHM payload, for example:
  `output/ohm_borders/global-2026-04-14/raw/overpass.json`
- A seed polity identified by Wikidata QID or exact OHM name
- Traversal limits:
  - `max_depth`
  - `max_nodes`

## First Run

Command shape:

```powershell
py -m pipeline borders extract-subgraph \
  --input output/ohm_borders/global-2026-04-14/raw/overpass.json \
  --seed-name "Roman Empire" \
  --run-id roman-empire-subgraph \
  --max-depth 3 \
  --max-nodes 400
```

Then run the standard OHM stages against the subset artifact directory:

```powershell
py -m pipeline borders parse --run-id roman-empire-subgraph --resume
py -m pipeline borders enrich --run-id roman-empire-subgraph --resume --enrich-names
py -m pipeline borders build --run-id roman-empire-subgraph --resume
py -m pipeline borders relations-run --run-id roman-empire-subgraph --resume
```

## Validation Before Import

Before importing to Laravel, inspect the subset closure report:

- `output/ohm_borders/<run_id>/subgraph/closure_report.json`

Validation checklist:

- confirm the resolved seed is the intended polity
- confirm the traversal parameters match the run you intended
- confirm no required relation targets are missing from the bundle
- confirm the graph was not truncated in an unexpected way by `max_depth` or `max_nodes`
- confirm the closure report does not report missing referenced Wikidata IDs before starting Laravel import steps

Import order for this workflow:

1. import border entities from the built OHM output
2. import relation entities from `relations_final/ohm_relation_entities.jsonl`
3. import and resolve relation hints from `relations_final/ohm_relation_hints.jsonl`

This order matters because the current Laravel relation import assumes entities land before relation resolution.

## Second Run

Use the same `run_id` with `--resume` when you want to continue a previous subset run without rebuilding finished artifacts.

Examples:

```powershell
py -m pipeline borders extract-subgraph \
  --input output/ohm_borders/global-2026-04-14/raw/overpass.json \
  --seed-name "Roman Empire" \
  --run-id roman-empire-subgraph \
  --max-depth 3 \
  --max-nodes 400 \
  --resume

py -m pipeline borders enrich --run-id roman-empire-subgraph --resume --enrich-names
py -m pipeline borders relations-run --run-id roman-empire-subgraph --resume
```

Use `--force` if any of these changed and you need a clean rebuild:

- the seed polity
- `max_depth`
- `max_nodes`
- the input global `overpass.json` path
- `raw_shard_size`
- extraction logic after code changes

## Notes

- This runbook describes the implemented workflow for the country subgraph extractor.
- A later Laravel plan may add retryable storage for unresolved relation endpoints, but this runbook assumes strict import order and bundle closure validation.
