# Audit Open Questions — Decision Record

> **Date:** 2026-06-12
> **Status:** Decisions accepted (some weights/timing pending owner tuning, flagged below)
> **Purpose:** Capture every open question raised by the read-only audit, the chosen answer and rationale, and the
> spec/plan that implements it. This is the authoritative decision log for the five remediation sub-projects.

## How to read this
Each decision lists: the question, the **decision**, the rationale, the implementing sub-project, and whether owner
sign-off is still needed. Sub-projects: **A** map optimization, **B** pipeline write-path, **C** confidence, **D** chronicle,
**E** temporal.

---

## Map

### D1 — Which endpoint should the live map use? GeoJSON bbox vs MVT tiles
**Decision:** Repoint the dashboard at the existing bbox GeoJSON endpoint with zoom-keyed simplification; **defer MVT**
until a customer SPA and real row counts justify it. → **Sub-project A.**
**Rationale:** The bbox endpoint already exists, is indexed, and is unused; repointing + simplification + caching is
low-effort and gets ~90% of the win with zero new infrastructure. MVT is a large investment that only pays off for a
high-traffic public map. **Owner sign-off:** run `SELECT count(*) FROM geometry_periods WHERE <year predicate>` for a dense
year; only build MVT if whole-year counts reach tens of thousands *and* the public SPA ships.

### D2 — Is the silent `year=1000` default intentional?
**Decision:** Make it explicit — require `year` (or a range) on `/entities/map` (422 if absent); remove the magic default
there. → **Sub-project A.**
**Rationale:** The client always has a year; the silent default only hides bugs like MQ-1.

### D3 — One feature per entity, or multiple period geometries?
**Decision:** One feature per entity (`DISTINCT ON`), with an `?all_periods=1` opt-out. → **Sub-project A.**
**Rationale:** Overlapping fills double-darken and break feature-state keyed by id.

### D4 — Is the OR-of-two-geometry-columns bbox match intentional?
**Decision:** Treat as a bug — filter and serialize the same `COALESCE(territory_geom, geom)` and index that expression.
→ **Sub-project A.**
**Rationale:** "Select by point, render by territory" is an inconsistency, not a feature; safe to change (no consumer yet).

### D5 — Does the product need antimeridian-crossing viewports?
**Decision:** Include longitude normalization + two-envelope OR in the bbox work (cheap insurance). → **Sub-project A.**
**Rationale:** Small, well-understood fix; avoids empty map strips across the Pacific once the bbox endpoint is live.

### D6 — Enforce one-primary-per-entity?
**Decision:** Yes — partial `UNIQUE (entity_id) WHERE is_primary` on aliases/locations/temporal-ranges, after a dedup
audit. → **Sub-project A.**
**Rationale:** The code already assumes it (`LIMIT 1` + recency tiebreaker); enforcing lets the indexes drop the sort and
prevents drift. Matches the geo-ref `one_active_primary_per_entity` pattern.

### D7 — Do admin tools rely on the extra map properties before trimming?
**Decision:** Trim `display_priority`/`icon_class`/`period_type`/`geometry_period_id` from the map payload (grep shows the
map render doesn't use them); keep behind a debug flag only if a consumer is later found. → **Sub-project A.**

---

## Pipeline

### D8 — Agent output directory: mount repo `output/` or write under `api/storage`?
**Decision:** Write under `api/storage/app/pipeline/agent_runs/<run_id>`. → **Sub-project B.**
**Rationale:** `api/` is already mounted at `/var/www/html`, so the path is container-visible with **zero** compose
changes; it's the Laravel-idiomatic location and matches existing `.vscode/tasks.json` usage.

### D9 — Relations import command + schema?
**Decision:** Reuse the relationship-hint flow (`pipeline:import-border-relations` / `resolve-relationships`) by emitting
hint records, not `import-borders`. → **Sub-project B.**
**Rationale:** That machinery already resolves names→ids and dedups. **Fallback:** a dedicated `agent:import-relations`
command if the hint schema is too heavy (raise before implementing that task).

### D10 — Should `chronicles:import` run automatically?
**Decision:** Yes — invoke it after `chronicle_writer` with `--sync` + return-code checking, behind the same
`--commit`/dry-run switch as the rest of the write path. → **Sub-project B.**
**Rationale:** DB persistence is the point; manual = forgotten (as today).

### D11 — State model: keep `TypedDict` + in-place mutation, or reducers?
**Decision:** Convert append-style fields to `Annotated` reducers as part of the checkpointing work (not speculatively now).
→ **Sub-project B.**
**Rationale:** Benign today (linear graph) but a hard prerequisite for safe checkpointing/parallelism.

### D12 — Verify `db.py` column assumptions?
**Decision:** Yes — add a startup schema check and make `db.py` distinguish query failure from empty result (log the
former). → **Sub-project B.**
**Rationale:** A wrong column name is silently swallowed (`except: return []`), which could mask a second failure.

### D13 — `style_validator` / `messy_research` / `wikipedia` / `deepagents`: implement or delete?
**Decision:** Delete the dead code (and the no-op `create_chronicle` flag); re-introduce as a scoped feature later if
wanted. → **Sub-project B.**
**Rationale:** Unwired modules the docs promise are exactly what produced this audit's drift.

---

## Confidence

### D14 — Replace the 0.95 floor; hard-block missing-Wikidata high-risk types?
**Decision:** Yes — evidence-based additive scoring (weights in spec C §3), recalibrated thresholds, and hard-block
`person`/`political_entity`/`dynasty` without a Wikidata match (wire the dead `requires_wikidata`). → **Sub-project C.**
**Owner sign-off:** the exact weights/cutoffs are tuned in the calibration test (C plan, Task 5) against seeded data.

---

## Chronicle

### D15 — `source_evidence`: structured jsonb or plain text?
**Decision:** `jsonb` array — migrate text→jsonb, add an `array` cast, keep the validator as array, emit a list from the
pipeline. → **Sub-project D.**
**Rationale:** Evidence is inherently a list; the agent already thinks in structured pointers; jsonb stays queryable.

### D16 — June-11 chronicle fields: user-editable or pipeline-only?
**Decision:** User-editable **and** pipeline-populated — extend FormRequests + all three serializers + a round-trip test,
and have `ImportChroniclesCommand` set them. → **Sub-project D.**
**Rationale:** They're already in the DTO/action/model/test; only the validation+serialization surfaces lag — clearly the
intended feature, half-wired.

---

## Temporal (cross-cutting)

### D17 — Open-ended / BCE bounds semantics?
**Decision:** Unknown bounds are unbounded (never excluded); BCE is a negative signed year; pad years on display. Applied
end-to-end (timeline coalesce, EntityBuilder ±∞ semantics, map/click ongoing handling, frontend date padding). →
**Sub-project E** (and the map/click pieces in A).
**Rationale:** Historically correct and closes a theme spanning all four areas in one ruling.

### D18 — Timeline freshness: observe relationship/location writes?
**Decision:** Add observers but debounce/batch during bulk imports (suppression flag + one batch rebuild). → **Sub-project E.**
**Rationale:** Controller-only rebuilds leave programmatic writes stale; batching prevents rebuild storms.

---

## Cross-references

| Decision | Spec | Plan |
|---|---|---|
| D1–D7 | [map-bbox-query-optimization-design](2026-06-12-map-bbox-query-optimization-design.md) | [plan](../plans/2026-06-12-map-bbox-query-optimization.md) |
| D8–D13 | [agentic-pipeline-write-path-design](2026-06-12-agentic-pipeline-write-path-design.md) | [plan](../plans/2026-06-12-agentic-pipeline-write-path.md) |
| D14 | [confidence-scoring-rework-design](2026-06-12-confidence-scoring-rework-design.md) | [plan](../plans/2026-06-12-confidence-scoring-rework.md) |
| D15–D16 | [chronicle-data-model-completion-design](2026-06-12-chronicle-data-model-completion-design.md) | [plan](../plans/2026-06-12-chronicle-data-model-completion.md) |
| D17–D18 | [temporal-semantics-unification-design](2026-06-12-temporal-semantics-unification-design.md) | [plan](../plans/2026-06-12-temporal-semantics-unification.md) |

## Pending owner sign-off
- **D1** — MVT vs GeoJSON-only, gated on the dense-year row count.
- **D14** — confidence weights + auto-commit cutoffs (tuned in the calibration test).
- **D9** — confirm the relationship-hint schema is emittable, else the dedicated-importer fallback.
