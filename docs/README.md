# Documentation Index

> **Plan execution status:** see [plans/STATUS.md](plans/STATUS.md) — a verified index of every plan (✅ executed / 🟡 partial / ⬜ not started). Fully-executed historical plans now live in [archive/superpowers-plans/](archive/superpowers-plans/).

This repository has a mix of current runbooks, reference docs, and older planning artifacts. If you want the project as it exists today, start with these documents in this order:

1. [../README.md](../README.md)
2. [architecture_overview.md](architecture_overview.md)
3. [implementation-docs/setup.md](implementation-docs/setup.md)
4. [../pipeline/README.md](../pipeline/README.md)
5. [implementation-docs/data_pipeline_architecture.md](implementation-docs/data_pipeline_architecture.md)

## Folder Guide

- `implementation-docs/`: current setup guides, runbooks, deployment docs, and implementation notes that still describe live behavior.
- `entity-model/`: current entity, relationship, timeline, and geometry model reference material.
- `reference/`: design references and proposal docs that are still useful, but do not describe the live app as-is.
- `archive/`: superseded or historical documents kept for decision history.
- `schemas/`: current payload and contract documentation for pipeline artifacts and API requests.
- `plans/`: the numbered product roadmap plus the live agent-driven backlog. See [plans/STATUS.md](plans/STATUS.md) for per-plan execution status.
- `superpowers/plans/` and `superpowers/specs/`: design and implementation artifacts created during agent-driven work. Only current-cycle (active or recently executed) plans remain here; historical ones moved to `archive/superpowers-plans/`.
- `ext/`: external reference material and supporting notes.

## Docs Map

### Current runbooks and live reference

- [architecture_overview.md](architecture_overview.md)
- [implementation-docs/setup.md](implementation-docs/setup.md)
- [implementation-docs/data_pipeline_architecture.md](implementation-docs/data_pipeline_architecture.md)
- [implementation-docs/ohm_country_subgraph_runbook.md](implementation-docs/ohm_country_subgraph_runbook.md)
- [implementation-docs/reference_tables.md](implementation-docs/reference_tables.md)
- [entity-model/README.md](entity-model/README.md)
- [entity-model/attributes.md](entity-model/attributes.md)
- [entity-model/diagrams.md](entity-model/diagrams.md)
- [entity-model/for-historians.md](entity-model/for-historians.md)
- [entity-model/for-geodata-contributors.md](entity-model/for-geodata-contributors.md)
- [entity-model/laravel-implementation-checklist.md](entity-model/laravel-implementation-checklist.md)

### Design references

- [reference/README.md](reference/README.md)
- [reference/implementation-docs/web_implementation_architecture.md](reference/implementation-docs/web_implementation_architecture.md)
- [reference/implementation-docs/game_inspired_ui_ux.md](reference/implementation-docs/game_inspired_ui_ux.md)
- [reference/implementation-docs/reference-timeline-schema.md](reference/implementation-docs/reference-timeline-schema.md)

### Historical context

- [archive/README.md](archive/README.md)
- [archive/implementation-docs/attributes_and_geometry_snapshots.md](archive/implementation-docs/attributes_and_geometry_snapshots.md)
- [archive/entity-model/schema-proposal-strict-write-derived-timeline.md](archive/entity-model/schema-proposal-strict-write-derived-timeline.md)

## Main Entry Points

- [architecture_overview.md](architecture_overview.md): runtime surfaces, routing, and repository responsibilities.
- [implementation-docs/setup.md](implementation-docs/setup.md): local setup, Docker services, commands, and route layout.
- [../pipeline/README.md](../pipeline/README.md): Python pipeline overview and working command entry points.
- [implementation-docs/data_pipeline_architecture.md](implementation-docs/data_pipeline_architecture.md): detailed scrape, OHM, import, and embedding flow.
- [implementation-docs/ohm_country_subgraph_runbook.md](implementation-docs/ohm_country_subgraph_runbook.md): current OHM subgraph extraction workflow.
- [entity-model/README.md](entity-model/README.md): entity model overview and companion references.
- [schemas/README.md](schemas/README.md): schema-level docs for import and API payloads.

## Notes on Currency

- `plans/` and many files under `superpowers/` capture decisions and implementation history; they are useful for rationale but are not the best source for current runtime behavior.
- For command syntax, prefer the README files and the command signatures in `api/app/Console/Commands/` and `pipeline/` over older plan docs.
