# Documentation Index

> **Plan status:** [plans/STATUS.md](plans/STATUS.md) is the verified index of every plan
> (✅ executed · 🟡 partial · ⬜ not started). Finished plans live in [archive/](archive/).

Start here, in order, for the project as it exists today:

1. [../README.md](../README.md) — repository overview and quick start
2. [architecture/system-overview.md](architecture/system-overview.md) — runtime surfaces, routing, responsibilities
3. [implementation-docs/setup.md](implementation-docs/setup.md) — local setup, Docker services, commands
4. [../pipeline/README.md](../pipeline/README.md) — Python pipeline overview
5. [architecture/data-pipeline.md](architecture/data-pipeline.md) — scrape → OHM → import → embedding flow

## Folder guide

| Folder | Contents |
|--------|----------|
| [architecture/](architecture/) | System and component architecture — the "how it's built" reference. |
| [implementation-docs/](implementation-docs/) | Operator runbooks and how-to guides (setup, deployment, OHM pipelines, agentic pipeline, data contribution). |
| [entity-model/](entity-model/) | Canonical entity / relationship / chronicle / geometry data-model reference. |
| [schemas/](schemas/) | Payload and contract docs for pipeline artifacts and API requests. |
| [reference/](reference/) | Forward-looking design references and proposals — useful for direction, **not** descriptions of the live app. |
| [plans/](plans/) | Live product roadmap and backlog. See [plans/STATUS.md](plans/STATUS.md) for execution status. |
| [superpowers/](superpowers/) | Agent-driven design specs (`specs/`) and implementation plans (`plans/`) for the current cycle. |
| [archive/](archive/) | Superseded or completed documents, kept for decision history. Not source of truth. |

## Architecture

- [architecture/system-overview.md](architecture/system-overview.md) — whole-system: runtime, routing, repositories
- [architecture/frontend-app.md](architecture/frontend-app.md) — the public `web/` Atlas SPA foundation
- [architecture/data-pipeline.md](architecture/data-pipeline.md) — all pipeline tracks + Laravel import layer
- [architecture/admin-map-editor.md](architecture/admin-map-editor.md) — admin entity editor and map UI
- [architecture/ohm-integration.md](architecture/ohm-integration.md) — OHM tile / MapLibre integration

## Operator runbooks ([implementation-docs/](implementation-docs/))

- [setup.md](implementation-docs/setup.md) · [deployment-runbook.md](implementation-docs/deployment-runbook.md)
- [data-contributor-guide.md](implementation-docs/data-contributor-guide.md) · [agentic-pipeline-runbook.md](implementation-docs/agentic-pipeline-runbook.md) · [pipeline-eval-iterations.md](implementation-docs/pipeline-eval-iterations.md)
- OHM: [ohm-border-extraction.md](implementation-docs/ohm-border-extraction.md) · [ohm-country-subgraph-runbook.md](implementation-docs/ohm-country-subgraph-runbook.md) · [ohm-egypt-collection-runbook.md](implementation-docs/ohm-egypt-collection-runbook.md) · [egypt-wikidata-fallback-runbook.md](implementation-docs/egypt-wikidata-fallback-runbook.md)

## Data model & contracts

- [entity-model/README.md](entity-model/README.md) — entity model overview and companion references
- [entity-model/entity-specification.md](entity-model/entity-specification.md) — the 30-type / 5-group canonical spec
- [schemas/README.md](schemas/README.md) — pipeline and API payload schemas

## Design references (not live)

- [reference/README.md](reference/README.md)
- [reference/game-inspired-ui-ux.md](reference/game-inspired-ui-ux.md) · [reference/reference-timeline-schema.md](reference/reference-timeline-schema.md) · [reference/ohm-cookbook.md](reference/ohm-cookbook.md)

## Notes on currency

- For command syntax, prefer the README files and the live signatures in `api/app/Console/Commands/` and `pipeline/` over older plan docs.
- `plans/`, `superpowers/`, and `archive/` capture decisions and history — useful for rationale, not for current runtime behavior. When in doubt, the code wins; then this index; then `plans/STATUS.md`.
