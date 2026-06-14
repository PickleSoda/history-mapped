# Confidence Scoring Rework — Implementation Plan

> **Status: ⬜ Not started** — as of 2026-06-15. See [STATUS.md](../../plans/STATUS.md).
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat 0.95 confidence floor with evidence-based scoring, recalibrate auto-commit thresholds, and hard-block high-risk entity types that lack a Wikidata match — so auto-commit requires real corroboration.

**Architecture:** `validate.py` computes a signal sum from enrichment data already on the candidate; weights, thresholds, and `requires_wikidata` policy flags live in `config.py`; the per-signal breakdown is attached to each `ValidationResult` and surfaced in the manifest. The approval-gate mechanics are unchanged — only the scores and a hard-block route.

**Tech Stack:** Python 3.11+, Pydantic, pytest.

**Spec:** [../specs/2026-06-12-confidence-scoring-rework-design.md](../specs/2026-06-12-confidence-scoring-rework-design.md)

**Depends on:** sub-project B (write path) — sequence after it.

---

## File structure

| File | Change |
|------|--------|
| `pipeline/agent/schemas/validation.py` | Add `confidence_breakdown` to `ValidationResult` |
| `pipeline/agent/config.py` | `CONFIDENCE_WEIGHTS`; recalibrated thresholds; `requires_wikidata` flags |
| `pipeline/agent/graph/nodes/validate.py` | `score_entity`/`score_relation`; hard block; drop the 0.95 seed |
| `pipeline/agent/graph/nodes/audit_logger.py` | Include breakdown per item |
| Tests | `pipeline/agent/tests/test_nodes_proposal.py`, `test_config.py` |

---

## Task 1: `confidence_breakdown` on `ValidationResult`

**Files:** Modify `pipeline/agent/schemas/validation.py`; Test `pipeline/agent/tests/test_schemas.py`

- [ ] **Step 1: Write the failing test** — `ValidationResult(..., confidence_breakdown={"base":0.35})` constructs and round-trips via `model_dump`.
- [ ] **Step 2: Run → FAIL.** `py -m pytest pipeline/agent/tests/test_schemas.py -v`
- [ ] **Step 3: Implement** — add `confidence_breakdown: dict[str, float] = {}` to `ValidationResult`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(agent): add confidence_breakdown to ValidationResult`

## Task 2: Weights, thresholds, and `requires_wikidata` in config

**Files:** Modify `pipeline/agent/config.py`; Test `pipeline/agent/tests/test_config.py`

- [ ] **Step 1: Write the failing test** — `CONFIDENCE_WEIGHTS` exists with the spec keys; the high-risk entity policies have `requires_wikidata: True`; thresholds match the recalibrated scale.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement**

```python
CONFIDENCE_WEIGHTS = {
    "base": 0.35, "wikidata_label": 0.25, "wikidata_desc": 0.10,
    "ohm_geometry": 0.15, "db_corroboration": 0.10, "date_overlap": 0.05,
    "ambiguous": -0.15, "missing_wikidata_high_risk": -0.30,
}
```

Set `requires_wikidata: True` on `person`/`political_entity`/`dynasty` in `ENTITY_RISK_POLICIES`; adjust
`auto_commit_threshold`s to the new scale (≈0.85/0.90/0.95 by risk).

- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(agent): evidence-based confidence weights and recalibrated thresholds`

## Task 3: `score_entity`/`score_relation` + hard block in `validate.py`

**Files:** Modify `pipeline/agent/graph/nodes/validate.py`; Test `pipeline/agent/tests/test_nodes_proposal.py`

- [ ] **Step 1: Write the failing tests** —
  (a) a zero-enrichment low-risk entity scores `< auto_commit_threshold` (no longer auto-commits);
  (b) a fully-corroborated entity (exact Wikidata + OHM + DB) auto-commits;
  (c) a `person` with no Wikidata is in `blocked_items` regardless of score.
- [ ] **Step 2: Run → FAIL** (today everything seeds 0.95).
- [ ] **Step 3: Implement** — `score_entity(enriched) -> (final, breakdown)` summing `CONFIDENCE_WEIGHTS` per present signal from the candidate's enrichment fields; `final = clamp(sum, 0, 1)`; remove the `0.95 +` seed. If `policy.requires_wikidata` and no Wikidata match → append to `blocked_items` with a reason. `score_relation` bases on endpoint resolution quality. Attach `breakdown` to the `ValidationResult`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(agent): evidence-based confidence scoring + hard-block high-risk without Wikidata`

## Task 4: Surface the breakdown in the manifest

**Files:** Modify `pipeline/agent/graph/nodes/audit_logger.py`; Test `pipeline/agent/tests/test_nodes_io.py`

- [ ] **Step 1: Write the failing test** — the manifest's validation section includes each item's `confidence_breakdown`, and the breakdown sums to its `system_confidence`.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — include `confidence_breakdown` (and the final score) per validated item in the manifest payload.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(agent): record confidence breakdown in manifest`

## Task 5: Calibration test (documents the chosen cutoffs)

**Files:** Test `pipeline/agent/tests/test_confidence_calibration.py` (new)

- [ ] **Step 1: Write the test** — run the scorer over representative candidates (no enrichment / partial / full) and assert the auto-commit/review/block split matches the intended policy; this test is the living record of the calibration decision.
- [ ] **Step 2: Run → PASS** (after Task 3) — adjust weights/thresholds in `config.py` until the split is correct, with the owner's sign-off.
- [ ] **Step 3: Commit** `test(agent): confidence calibration policy`

---

## Self-review (coverage)

- PP-5 (flat floor) → T2, T3. Dead `requires_wikidata` → T2, T3 (wired + hard block). Transparency → T1, T4. Calibration → T5. All spec requirements mapped.

## Execution handoff

Subagent-driven recommended. Sequence after sub-project B. Task 5's weights are owner-tunable — land the mechanism (T1–T4), then tune in T5.
