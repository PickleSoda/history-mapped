# Confidence Scoring Rework — Design Spec

> **Date:** 2026-06-12
> **Status:** Design (approved) — ready for implementation planning
> **Area:** `pipeline/agent/graph/nodes/validate.py`, `config.py`, `schemas/`.
> **Source:** bug report PP-5 (confidence floor) + the dead `requires_wikidata` finding.
> **Sub-project:** C of the audit-remediation set. Depends on sub-project B (the write path must work for "committed" to mean something).

## 1. Problem

`validate.py` seeds entity confidence at a flat `0.95` plus enrichment-only bonuses, so an entity with zero external
corroboration already clears the auto-commit thresholds for the five low-risk types and every relation. The approval gate
— named and documented as human-in-the-loop — is effectively an automatic rubber stamp, and confidence is decoupled from
evidence. The `requires_wikidata` blocking penalty is dead code (no policy sets the key).

## 2. Goals / Non-goals

**Goals**
- `final_confidence` reflects **evidence quality**, not a constant floor.
- Auto-commit requires real corroboration; unverified items go to human review.
- High-risk entity types without a Wikidata match are hard-blocked.
- The scoring is transparent (per-signal contributions visible in the manifest).

**Non-goals**
- Changing the graph topology or the approval-gate node mechanics (only the scores + thresholds + a block rule).
- The write path (sub-project B).

## 3. Accepted decision — the scoring model

Replace the flat floor with an additive, signal-based score, separating the three confidence channels the original design
called for:

- **`llm_confidence`** — what the extractor reported (kept for audit, not auto-committed on alone).
- **`system_confidence`** — deterministic signal sum (below).
- **`final_confidence`** — `clamp(base + system_confidence, 0, 1)`.

**Entity signals (suggested starting weights — owner-tunable):**

| Signal | Δ |
|---|---|
| base ("an LLM proposed it") | +0.35 |
| exact Wikidata label match | +0.25 |
| Wikidata description/type agreement | +0.10 |
| OHM geometry resolved | +0.15 |
| existing-DB corroboration | +0.10 |
| date overlap with a known range | +0.05 |
| ambiguous (≥2 Wikidata candidates) | −0.15 |
| missing Wikidata on a high-risk type | −0.30 (and **hard block** — see below) |

**Relations:** start at a base reflecting endpoint resolution quality (both endpoints resolved to DB ids → higher), not a flat 0.95.

**Hard block:** `person`/`political_entity`/`dynasty` (the high-risk set) with no Wikidata match are routed to
`blocked_items` regardless of score (wire the currently-dead `requires_wikidata` policy key, set it for these types).

**Thresholds (recalibrated to the new scale):** auto-commit ≈ ≥0.85 low-risk, ≥0.90 medium, ≥0.95 high — confirmed against
seeded data before merge.

## 4. Architecture

`validate.py` computes the signal sum from data already on the `EnrichedCandidate` (Wikidata match, OHM geometry,
`existing_entity`, date fields). `config.py` holds the weights + thresholds + the `requires_wikidata` policy flags. The
score breakdown is attached to each `ValidationResult` so `audit_logger` can surface it.

### 4.1 Components

- **`schemas/validation.py`** — `ValidationResult` gains a `confidence_breakdown: dict[str, float]` field.
- **`config.py`** — `CONFIDENCE_WEIGHTS` dict; recalibrated `ENTITY_RISK_POLICIES`/relation thresholds; set
  `requires_wikidata: True` for the high-risk entity types.
- **`validate.py`** — `score_entity(enriched) -> (final, breakdown)` and `score_relation(...)`; apply the hard-block;
  stop seeding 0.95.
- **`audit_logger`** — include the breakdown in the manifest per item.

## 5. Data flow

`validate` reads enrichment results already on state → computes `system_confidence` + breakdown → `final_confidence` →
`build_diff`/`approval_gate` use `final_confidence` exactly as today (no gate-mechanics change), except hard-blocked items
go straight to `blocked_items`.

## 6. Error handling

- Missing enrichment fields contribute 0 (not a crash).
- Hard-blocked items are recorded with a reason in the manifest, not silently dropped.

## 7. Testing

- A zero-enrichment entity of a low-risk type scores **below** the auto-commit threshold (no longer auto-commits).
- A fully-corroborated entity (exact Wikidata + OHM + DB) auto-commits.
- A high-risk type with no Wikidata is in `blocked_items` regardless of score.
- The `confidence_breakdown` appears in the manifest and sums to `system_confidence`.
- Threshold-calibration test against the seeder fixtures (documents the chosen cutoffs).

## 8. Sequencing (feeds the plan)

1. Add `confidence_breakdown` to the schema + weights/thresholds to config.
2. Implement `score_entity`/`score_relation` + hard block in `validate.py`.
3. Surface the breakdown in the manifest.
4. Calibration test + threshold tuning.

## 9. Risks

- **Threshold calibration** is judgment — land the mechanism first, then tune weights/cutoffs against real seeded data
  with the owner; keep weights in config so tuning is a one-file change.
- **Depends on sub-project B** — until commits actually land, "auto-commit" has no observable effect; sequence C after B.
