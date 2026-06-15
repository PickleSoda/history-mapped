# Archived Docs

This folder contains superseded or historical documents that are kept for implementation history and decision context.

## Current contents

- [implementation-docs/attributes_and_geometry_snapshots.md](implementation-docs/attributes_and_geometry_snapshots.md): pre-cutover planning model for JSONB attributes and `geometry_snapshots`
- [implementation-docs/historical_entity_agentic_pipeline_plan.md](implementation-docs/historical_entity_agentic_pipeline_plan.md): superseded DeepAgents-centric pipeline plan; the shipped design is the LangGraph agent (see `../implementation-docs/agentic-pipeline-runbook.md`)
- [entity-model/schema-proposal-strict-write-derived-timeline.md](entity-model/schema-proposal-strict-write-derived-timeline.md): historical proposal that influenced the normalized entity model and derived timeline pipeline

### superpowers-plans/

Fully-executed (April–May 2026 cycle) and superseded agent-driven plans, moved here on 2026-06-15. They are verified-shipped or obsolete; kept for decision history. See [../plans/STATUS.md](../plans/STATUS.md) for the verification record. Notable: `2026-04-14-ohm-concurrent-stages-plan.md` and `2026-04-07-legacy-erasure-inventory.md` are superseded/audit-only; `2026-06-12-chronicle-dashboard-display.md` was superseded by the `web/` atlas implementation.

These files are not the source of truth for current runtime behavior.
Use [../README.md](../README.md) for the live docs map.
