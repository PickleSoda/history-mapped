# Pipeline Data-Quality Remediation

> **Status: ⬜ Not started** — created 2026-06-18.
> **Scope:** `pipeline/agent/` (LangGraph entity/relation/chronicle pipeline) + the Laravel import/enrichment path.
> **Audit basis:** Empirical audit of a real langgraph-generated dataset (`output/history-mapped.sql`,
> 2.2 MB pg_dump dated 2026-06-18) loaded into a fresh schema and queried directly. Numbers below are the
> **measured baseline** to re-measure against after each fix.
> **Related plans:** ranking overlaps [`../superpowers/plans/2026-06-12-confidence-scoring-rework.md`](../superpowers/plans/2026-06-12-confidence-scoring-rework.md);
> structural pipeline work in [`agentic-pipeline-improvements.md`](agentic-pipeline-improvements.md).

---

## 1. How the baseline was captured

The dump is a data-only `pg_dump` of langgraph output. To inspect it in isolation:

```bash
# 1. Fresh schema, no seeders ("minimal" state — there is no --minimal flag; this is the equivalent)
docker compose -f docker/docker-compose.yml exec -T app php artisan migrate:fresh --force

# 2. Filter out tables a fresh DB already populates (would collide on PK)
awk '/^COPY public\.(spatial_ref_sys|migrations) / {skip=1}
     skip==1 && /^\\\.$/ {skip=0; next} skip==1 {next} {print}' \
  output/history-mapped.sql > output/history-mapped.filtered.sql

# 3. Load with FK/triggers relaxed (data-only COPY order can violate FKs)
docker compose -f docker/docker-compose.yml cp output/history-mapped.filtered.sql db:/tmp/import.sql
docker compose -f docker/docker-compose.yml exec -T db bash -c \
  "(echo 'SET session_replication_role = replica;'; cat /tmp/import.sql) \
   | psql -U history-mapped -d history-mapped -v ON_ERROR_STOP=1 -q"
```

Dataset size: **884 entities, 382 relationships, 37 chronicles, 685 chronicle entries.**

---

## 2. Measured baseline (the problems)

### P1 — OHM georefs are pointed at the wrong entities

| entity_group | entities | with OHM ref |
|---|---|---|
| PLACE (cities, monuments) | 96 | **0** |
| POLITY (countries, dynasties) | 554 | 59 |
| EVENT | 221 | 8 |

The 96 PLACE entities — the ones that most obviously need a location — have **zero** OHM refs, while refs landed
on polities and events. Root cause is by design: [`resolve_ohm.py`](../../pipeline/agent/graph/nodes/resolve_ohm.py)
gates on `_GEO_TYPES = _POLITY_TYPES | _EVENT_TYPES` and **deliberately excludes bare city names** (the inline
comment cites the "Rome OH / Gaza IA" Nominatim collision and defers era-aware place geocoding). Overall only
166/884 (19%) have any geo-ref; `territory_geom` is NULL for 100% of `entity_locations` (884/884).

### P2 — Dates: fabricated precision + sign errors

- **Every** exact date is `YYYY-01-01` (e.g. Abbasid Caliphate `750-01-01`, Baghdad `762-01-01`). Jan-1 is
  fabricated when only a year is known. `start_year` is correct; `start_date` is false precision.
- `date_method` and `date_confidence` are **NULL for 100%** of `entity_temporal_ranges` (709) and entities (884),
  so nothing flags the approximation.
- 190/709 ranges have `start_year = end_year`.
- CE/BCE sign errors occur intermittently (LLM mis-signs years despite the prompt forbidding it).

### P3 — Ranking / scoring is undifferentiated or absent

- Chronicles: **31/37 (84%) have `impact_score = 98`**; only 4 distinct values exist.
- `entities.confidence`, `entities.display_priority` — **NULL for 100%** (884/884).
- `entity_locations.location_confidence` — **NULL for 100%**.
- No pipeline node writes `impact_score`/`confidence`/`display_priority` (`grep` finds zero references in nodes);
  values are LLM-emitted or constant. This is missing implementation, not a tuning problem.

### P4 — Relations & entities: low yield, incomplete

- **423/884 entities (48%) are orphans** — participate in zero relationships.
- 259/382 relations (68%) have no end date; 43 (11%) no start.
- FK integrity is clean (0 dangling), all relations typed/described/cited — the *structure* is fine; *recall* is not.

### P5 — Generated text is shallow

[`generate_content.py`](../../pipeline/agent/graph/nodes/generate_content.py) writes summaries for **all entities
in one JSON blob in a single call** (tiny token budget each), passes only `label/type/wikidata_description/dates`
as context (**not the source transcript, not the entity's relations**), and never generates the `significance`
column. Output is effectively a paraphrase of the Wikidata one-liner.

---

## 3. Diagnosis

The failures are **whole-field / inverted-logic**, not random noise. That means a retry loop alone fixes almost
none of them — the data only improves when missing logic is written and inverted targeting is corrected. Looping
helps exactly one axis: **recall** (P4, and the place-resolution fallback within P1). Everything else is a
deterministic fix or a prompt+context fix that belongs in code regardless of framework.

Target georef matrix (decided 2026-06-18) — **point only, never a territory polygon**:

| group | georef point | territory polygon |
|---|---|---|
| POLITY | ✅ | ❌ |
| PLACE | ✅ | ❌ |
| EVENT | ✅ (Nominatim, else Wikidata coords) | ❌ |
| person / culture / economy | ❌ | ❌ |

---

## 4. Fix plan

> **Progress (2026-06-18):** F1–F4 implemented. **F1** (gate incl. PLACE; territory was already never generated),
> **F2** (`_sign_corrected`), **F3** (`_wikidata_date` precision) — Python, logic-verified standalone; full
> `pytest` pending a venv (host has no pip/venv/network). **F4 done & verified in the app container:** **F4a**
> `display_priority = impact_score` in `ImportEntityJob::normalizePipelineRecord` (verified: import probe sets it);
> **F4b** chronicle impact de-saturation (`EnrichChronicleMetadataAction::computeChronicleImpact`, **0.7·peak +
> 0.3·mean** of involved-entity impacts — entry-count breadth was tried first but barely moved the needle since
> these chronicles are large). Verified on the live snapshot: biggest impact bucket dropped from **31/37 (84%)**
> to **10/37 (27%)**, spread 74–96, 10 distinct values. Unit-tested + full suite green (185 passed).
> Confidence/`date_*` enum population deferred to [confidence-scoring-rework](../superpowers/plans/2026-06-12-confidence-scoring-rework.md).
>
> **F5** (`generate_content.py`): rewritten to summarise entities in small chunks (`ENTITY_CHUNK_SIZE=6`) with rich
> per-entity context (source-event text + its relationships + Wikidata gloss + dates), producing both `summary`
> **and** `significance`; `EnrichedCandidate.significance` added, `commit_writer` emits it, `EntityData` already
> persists it. Relation descriptions kept as one pass. Parse/chunk logic verified standalone; pytest + a real LLM
> run pending a venv.
>
> **F6** (recall loop): new `completeness_critic` node + `route_after_critic` — re-reads the (cleaned) transcript
> with the current candidates, adds only missing/deduped entities & relations, and self-loops up to
> `MAX_CRITIC_ITERATIONS=2` (stops early when a pass finds nothing new). Wired as
> `extract_candidates → completeness_critic → {loop|done→db_lookup}`; state gains `critic_iterations`/`critic_done`.
> Decision (2026-06-18): **bounded in-DAG loop**, not the standalone MCP/agent rewrite — cheapest way to lift recall
> and prove the concept first. Dedup/cap/routing verified standalone + unit tests added; pytest + LLM run pending.
>
> **Post-eval round (2026-06-18, after a live run on `output/sample_transcript.txt`):** fixed adjacent issues the
> run surfaced — (A) OHM name-adoption replaced by **alias recording** in `resolve_ohm._record_ohm_alias` (keep the
> readable display name, e.g. `Carthage` not OHM's `Carthāgō`; ends garbled near-duplicates); (B) **orphan-targeting**
> in `completeness_critic` (computes entities with no relations, prompts to connect each — Carthage went from 0
> relations to connected); (C) critic **precision** guard (no `member_of_dynasty` to a republic/state); (E) F5 prompt
> relaxed so recognised entities always get summary+significance. Verified end-to-end: readable names + aliases, no
> orphaned Carthage, no bad `member_of_dynasty`, all created entities have content. 128 agent tests pass (run via the
> uv venv: `pipeline/.venv` on managed CPython 3.12).
>
> **Remaining follow-ups:** (1) true single-entity dedup of `Carthage` vs `Carthaginian Empire` (rely on the Laravel
> importer's OHM-id dedup, or add OHM-id dedup in-pipeline); (2) Wikidata **namesake disambiguation** — "Lucius
> Aemilius Paullus" resolved to a later namesake's dates; needs era-aware ranking even on non-ambiguous top matches.
>
> **Env gotchas:** (1) Docker Desktop bind mount caches files present at container start — after editing an
> existing `api/` file, `docker compose restart app` before running tests or the container serves the stale copy.
> (2) Re-running tests must wait for `app` to be `running` after a restart.

| # | Fix | Where | Type | Acceptance |
|---|---|---|---|---|
| F1 | Add PLACE to the OHM gate; force point-only for POLITY/PLACE/EVENT; era + Wikidata-`qid` anchoring to beat name collisions | [`resolve_ohm.py`](../../pipeline/agent/graph/nodes/resolve_ohm.py) | logic | PLACE OHM coverage ≫ 0; no territory geometry written; no georefs on person/culture/economy |
| F2 | CE/BCE sign corrector — when Wikidata returns a date, trust its sign/year over the LLM | [`resolve_wikidata.py`](../../pipeline/agent/graph/nodes/resolve_wikidata.py) | deterministic | no `start_year > end_year`; sign matches Wikidata where available |
| F3 | Year-only dates → stop fabricating `-01-01` (precision-aware Wikidata date extraction) | [`wikidata.py`](../../pipeline/agent/tools/wikidata.py) (`_wikidata_date`) | deterministic | year-precision Wikidata facts store no fake month/day. **Done.** `date_method`/`date_confidence` population moved to F4 (needs JSONL→importer plumbing) |
| F4 | Deterministic ranking (impact/confidence/priority) + populate `date_method`/`date_confidence` | `EnrichChronicleMetadataAction` (Laravel) + entity scorer + JSONL/importer plumbing | deterministic | `impact_score` spread > 4 values; `confidence`/`display_priority`/`date_confidence` non-NULL. See [confidence-scoring-rework](../superpowers/plans/2026-06-12-confidence-scoring-rework.md) |
| F5 | Rich content: feed source text + relations per entity; generate summary **and** significance; depth target; chunked calls | [`generate_content.py`](../../pipeline/agent/graph/nodes/generate_content.py) | prompt+context | `significance` populated; summaries cite source events; length above one-liner |
| F6 | Recall loop: extract → completeness-critic over raw transcript → re-extract until dry | new agentic step | agentic | orphan-entity rate ≪ 48%; more relations per transcript |

**Sequencing:** F1 → F2 → F3 → F4 → F5 are in-place (deterministic / prompt) and need no architecture change; do
them first and re-measure. F6 is the agentic step and the honest test of whether tool-using iteration raises yield;
it is the justification for the MCP/agent investment discussed in [agentic-pipeline-improvements.md](agentic-pipeline-improvements.md).

## 5. Re-measure protocol

After each fix, re-run the pipeline on the same transcripts, reload, and re-run the §2 queries against the
baseline numbers. The §1 load procedure is the reset.

## 6. Post-F1–F6 validation (2026-06-19) — three new systematic fixes

Validating the F1–F6 work end-to-end on a clean DB across 10 comprehensive transcripts (christianity,
epidemics, renaissance, islamic_golden_age, norse_culture, silk_road, greek_philosophy, ancient_egypt,
roman_republic, mongol_empire) surfaced three more systematic bugs, now fixed:

- **G1 — off-taxonomy entity types silently blocked (~20% of candidates).** Despite the prompt the LLM emits
  generic/synonym types — `polity`/`state`/`place` for backbone polities (Roman Empire, Roman Republic,
  Carthage, Italy), `religion` for Christianity, bare `event` for the Punic Wars. `validate.ALLOWED_ENTITY_TYPES`
  dropped them, and their relations went unresolved at import (roman_republic committed **0 of 11** relations).
  Fix: normalize generic→canonical at `CandidateEntity` construction (covers extractor **and** critic),
  label-aware for bare events; countries/regions → `political_entity` (no dedicated type). →
  [`schemas/entities.py`](../../pipeline/agent/schemas/entities.py) `normalize_entity_type`.
- **G2 — era-rerank demoted real ancient cities.** Same-name Wikidata candidates tie on label score, so the era
  tie-break runs and penalises far-from-era dates (≥400y, −0.4); a city's deep-BCE inception is always far, so
  the real Jerusalem (Q1218) was pushed below a dateless modern namesake (Q10540001) and got no geo. Fix: skip
  era-rerank for persistent place types (city/monument/institution). →
  [`resolve_wikidata.py`](../../pipeline/agent/graph/nodes/resolve_wikidata.py).
- **G3 — relations to non-extracted entities orphaned their endpoints.** The critic emits relations to things it
  never extracts ("Leonardo authored Mona Lisa", no Mona Lisa entity); validate drops them, orphaning the person
  (29% orphans, 43 notable people). Fix: critic prompt now requires referential integrity, plus a deterministic
  backstop that materialises a missing endpoint with a relationship-inferred type (or drops the un-typeable
  dangler). → [`completeness_critic.py`](../../pipeline/agent/graph/nodes/completeness_critic.py).

**Measured impact (clean 10-transcript run, gpt-4o):** entities 246→302, relationships 107→160 (+50%),
geo_refs 69→111, orphan rate 37%→29%, **zero off-taxonomy types in the DB**, relation import resolution ~50%→~94%.
Backbone polities now created with correct types; Jerusalem→Q1218 and Samarkand→Q5753 (was stray QIDs) with geo.
Dates remain clean (62 BCE / 128 CE correctly signed, zero fabricated `-01-01`); chronicle impact spans 74–93.

**Remaining follow-ups (still open):** (1) `Carthage`/`Carthaginian Empire` single-entity dedup;
(2) Wikidata namesake disambiguation on non-ambiguous top matches (Paullus wrong dates);
(3) **diacritic-insensitive Wikidata search** — "Reykjavik" (unaccented in the transcript) doesn't surface the
canonical "Reykjavík" Q1764, so it resolves to an obscure same-spelling item with no coordinates (1 of 302
entities); search should fold diacritics or try an accent-normalised query;
(4) re-validate G1–G3 (especially the G3 orphan-rate drop) once the pipeline's model config is settled — the
2026-06-19 switch to free OpenRouter tiers means the next run uses different models than this measurement.
