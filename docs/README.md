# Documentation Index

This repository has a mix of current runbooks, reference docs, and older planning artifacts. If you want the project as it exists today, start with these documents in this order:

1. [../README.md](../README.md)
2. [architecture_overview.md](architecture_overview.md)
3. [implementation-docs/setup.md](implementation-docs/setup.md)
4. [../pipeline/README.md](../pipeline/README.md)
5. [implementation-docs/data_pipeline_architecture.md](implementation-docs/data_pipeline_architecture.md)

## Folder Guide

- `implementation-docs/`: current setup guides, runbooks, architectural notes, and deployment docs.
- `entity-model/`: entity, relationship, timeline, and geometry model reference material.
- `schemas/`: current payload and contract documentation for pipeline artifacts and API requests.
- `plans/`: older implementation plans and rollout notes.
- `superpowers/plans/` and `superpowers/specs/`: design and implementation artifacts created during agent-driven work.
- `ext/`: external reference material and supporting notes.

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
