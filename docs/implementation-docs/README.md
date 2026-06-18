# Implementation Docs — Operator Runbooks & Guides

How-to guides for setting up, deploying, and running the system. For *how it's built* (architecture),
see [../architecture/](../architecture/); for the data model, see [../entity-model/](../entity-model/).

## Setup & deployment

- [setup.md](setup.md) — local dev: Docker stack, services, commands, route layout.
- [deployment-runbook.md](deployment-runbook.md) — canonical GHCR → DigitalOcean deploy (App Platform or Droplet + Compose).

## Agentic pipeline

- [agentic-pipeline-runbook.md](agentic-pipeline-runbook.md) — the 15-node LangGraph agent: nodes, commands, env, risk policies, LangGraph Studio, known defects.
- [pipeline-eval-iterations.md](pipeline-eval-iterations.md) — narrative log of agent-pipeline hardening and the eval harness.

## OHM data pipelines

- [ohm-border-extraction.md](ohm-border-extraction.md) — global OHM border pipeline, step by step (internals).
- [ohm-country-subgraph-runbook.md](ohm-country-subgraph-runbook.md) — extract one country subgraph from a global OHM dump.
- [ohm-egypt-collection-runbook.md](ohm-egypt-collection-runbook.md) — build the Egypt collection from a local OHM export.
- [egypt-wikidata-fallback-runbook.md](egypt-wikidata-fallback-runbook.md) — curated Wikidata fallback when OHM coverage is thin.

## Data contribution

- [data-contributor-guide.md](data-contributor-guide.md) — JSONL schema, Python + Laravel import commands, workflows, debugging.
