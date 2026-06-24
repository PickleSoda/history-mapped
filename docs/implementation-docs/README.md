# Implementation Docs — Operator Runbooks & Guides

How-to guides for setting up, deploying, and running the system. For *how it's built* (architecture),
see [../architecture/](../architecture/); for the data model, see [../entity-model/](../entity-model/).

## Setup & deployment

- [setup.md](setup.md) — local dev: Docker stack, services, commands, route layout.
- [deployment-runbook.md](deployment-runbook.md) — canonical GHCR → DigitalOcean deploy (App Platform or Droplet + Compose).

## Admin AI agent

- [admin-ai-agent.md](admin-ai-agent.md) — route-bound AI editing assistant in the admin: propose→preview→confirm flow, tool list, provenance, OpenRouter config, and retention (`ai:prune-proposals`).

## Agentic pipeline

- [agentic-pipeline-runbook.md](agentic-pipeline-runbook.md) — the 15-node LangGraph agent: nodes, commands, env, risk policies, LangGraph Studio, known defects.
- [pipeline-eval-iterations.md](pipeline-eval-iterations.md) — narrative log of agent-pipeline hardening and the eval harness.
- [entity-reresolution.md](entity-reresolution.md) — fix already-committed entities' QID/type/location/dates in place (preserving relations) when a re-run won't reach them.
- [data-quality-runbook.md](data-quality-runbook.md) — symptom-indexed fixes for bad committed data: geometry/location model, over-anchored dates, century-parse years, event locations, malformed names.
- [content-data-transfer.md](content-data-transfer.md) — ship hand-fixed DB content (not the JSONL) from local Postgres to the prod droplet: cleaned data-only dump + atomic full-replace loader.

## OHM data pipelines

- [ohm-border-extraction.md](ohm-border-extraction.md) — global OHM border pipeline, step by step (internals).
- [ohm-country-subgraph-runbook.md](ohm-country-subgraph-runbook.md) — extract one country subgraph from a global OHM dump.
- [ohm-egypt-collection-runbook.md](ohm-egypt-collection-runbook.md) — build the Egypt collection from a local OHM export.
- [egypt-wikidata-fallback-runbook.md](egypt-wikidata-fallback-runbook.md) — curated Wikidata fallback when OHM coverage is thin.

## Data contribution

- [data-contributor-guide.md](data-contributor-guide.md) — JSONL schema, Python + Laravel import commands, workflows, debugging.
