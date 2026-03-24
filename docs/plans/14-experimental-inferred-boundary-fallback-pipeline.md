# 14 — Experimental Inferred Boundary Fallback Pipeline

## Objective
Design an experimental, license-safe pipeline that generates **machine-inferred historical boundary layers** when OpenHistoricalMap (OHM) has no usable boundary geometry for a polity and **no human review** is available.

The output of this pipeline is **not canonical territory data**. It is an inferred overlay intended to improve map coverage while preserving a strict separation from verified entity geometry.

## Scope
- Experimental inferred boundary generation for missing polity/date geometry.
- License-safe ingestion from open or explicitly permitted sources only.
- Fully automated acceptance or abstention logic.
- Separate storage and serving path for inferred geometry.

## Out of Scope
- Replacing OHM as the canonical boundary source.
- Human review workflows.
- Auto-publishing inferred geometry back to OHM.
- Use of proprietary raster atlases, traced tiles, or unclear-license derivatives.
- Non-polity inferred geometry in the first experiment.

## Deliverables
1. Source compliance registry and enforcement gate.
2. OHM missing-boundary inventory for `political_entity`.
3. At least one working inference prototype with offline backtest results.
4. Dedicated inferred snapshot storage model and API contract.
5. Quantitative promotion / stop criteria for future rollout decisions.

## Dependencies
- OHM boundary access and date filtering already documented in [docs/ohm_integraton_guide.md](docs/ohm_integraton_guide.md).
- Existing geometry snapshot concepts in [docs/plans/attributes_and_geometry_snapshots.md](docs/plans/attributes_and_geometry_snapshots.md).
- Existing pipeline architecture in [docs/data_pipeline_architecture.md](docs/data_pipeline_architecture.md).

## Why This Exists
OHM is the preferred reference layer, but historical border coverage is uneven across time and region. In some periods we know a polity existed, but no usable territory polygon is present.

Without a fallback, the application either:
- shows no border at all, or
- relies on legally or historically unsafe sources.

This plan explores a third path:
- use only open / compatible-license evidence,
- infer a likely control surface automatically,
- publish only high-confidence results,
- abstain completely when the evidence is weak.

## Hard Constraints

### 1) No human review
This experiment assumes the system must either:
- accept an inferred layer automatically, or
- reject / abstain automatically.

There is no manual validation stage in the critical path.

### 2) License-safe only
The experiment must not ingest, vectorize, trace, or derive machine output from closed or unclear-license map products.

This excludes workflows like:
- scraping raster map tiles from all-rights-reserved sites,
- tracing proprietary atlases,
- using non-redistributable geometry as model input for stored output.

Closed-license atlases may be useful as research references outside the pipeline, but they must not be part of automated data generation.

### 3) Inferred output is not canonical
Inferred layers must be stored and rendered as a separate product class from verified geometries.

They must carry explicit metadata such as:
- `geometry_origin = inferred`
- `inference_method`
- `confidence_score`
- `source_bundle`
- `generated_at`
- `model_version`

## Success Criteria
The experiment is successful if it can:
1. Detect OHM gaps automatically.
2. Generate plausible inferred polygons for a subset of missing polity/date combinations.
3. Reject low-confidence cases automatically.
4. Keep all inferred output separate from canonical entity geometry.
5. Produce enough provenance and metrics to compare methods objectively.

## Non-Goals
This experiment does **not** aim to:
- replace OHM as the source of truth,
- create historian-grade exact borders,
- auto-publish edits back to OHM,
- resolve every polity in every era,
- infer borders from proprietary map imagery.

## Proposed Product Behavior
When a map view requests a polity boundary for date `t`:

1. Use verified geometry if available.
2. Else check OHM-derived geometry snapshots.
3. Else check inferred-layer snapshots.
4. If no inferred snapshot passes the confidence threshold, render nothing.

This is a **hybrid abstention model**: no border is preferable to a low-confidence border.

## Experimental Architecture

```text
OHM / open datasets / terrain / places / text constraints
                │
                ▼
      Compliance gate + provenance manifest
    │
    ▼
        Gap detection stage
                │
                ▼
      Candidate evidence bundle
                │
                ▼
      Inference engines (parallel)
      - temporal interpolation
      - influence field growth
      - constrained Voronoi
      - text constraint geometry
      - region occupancy model
                │
                ▼
        Candidate polygon set
                │
                ▼
    Scoring + topology validation
                │
        ┌───────┴────────┐
        ▼                ▼
   publish inferred   abstain / drop
        │
        ▼
 inferred_geometry_snapshots
```

## Source Policy

### Allowed source classes
Only openly licensed or explicitly permitted source classes may feed the experiment:
- OHM-derived objects and metadata
- Wikidata / Wikipedia-derived structured context
- Natural Earth-like open basemaps where license is compatible
- openly licensed historical GIS datasets
- openly licensed coastlines, rivers, elevation, and hydrography
- project-authored derived datasets generated from allowed inputs

### Required source registry
Before any ingestion, maintain a machine-readable source registry with fields like:
- `source_key`
- `license`
- `reuse_allowed`
- `derivative_allowed`
- `commercial_allowed`
- `attribution_required`
- `geometry_allowed`
- `text_allowed`
- `raster_allowed`
- `notes`

Only sources with `reuse_allowed = true` and compatible derivative terms may be used for geometry generation.

### Compliance gate
Before a source can participate in inference, the pipeline must enforce all of the following:
- allowlist-only ingestion: unknown sources are rejected by default
- derivative-use eligibility must be explicit, not implied
- attribution requirements must be machine-readable and exportable with the output
- a per-run provenance manifest must record exact source versions used to generate each snapshot
- unclear or missing license metadata must cause hard rejection

No inference job should start until the compliance gate succeeds for the entire source bundle.

## Candidate Inference Methods
The experiment should compare several automated methods rather than betting on one.

### Method A — Temporal interpolation
Use when the same polity has usable boundary geometry before and after the target date.

Approach:
- choose nearest valid snapshots at `t1 < t < t2`
- normalize topology and CRS
- align polygons by overlap / centroid / adjacency
- interpolate a control surface, then polygonize
- penalize large wars / successor-state discontinuities

Best for:
- relatively continuous states
- modest temporal gaps

Weaknesses:
- poor performance for collapse, partition, conquest, or dynastic breaks

### Method B — Capital-centered influence fields
Estimate likely control from capitals and key settlements.

Approach:
- seed with capital, major cities, forts, ports, and administrative centers
- compute travel-cost expansion using terrain, rivers, coasts, and passes
- stop where competing polity influence exceeds local control score
- polygonize the winning control surface

Best for:
- empires and kingdoms with known urban hierarchy

Weaknesses:
- tends to over-smooth frontiers
- may confuse influence with sovereignty

### Method C — Constrained Voronoi / weighted partitioning
Partition the landscape using known settlements and administrative sites.

Approach:
- construct weighted Voronoi regions from polity-associated places
- weight by capital status, settlement class, route connectivity, and persistence
- clip by hydrographic / mountain barriers and coastlines
- dissolve contiguous cells into candidate territory

Best for:
- dense settlement networks
- regional approximation where no direct borders exist

Weaknesses:
- can create artificial straight-line boundaries in sparse areas

### Method D — Text constraint geometry
Convert spatial statements into machine-usable constraints.

Approach:
- parse text like “north of the Danube”, “in upper Mesopotamia”, or “between X and Y”
- geocode named rivers, mountain ranges, cities, and regions
- convert each claim into spatial masks / inclusion / exclusion zones
- intersect constraints with method A/B/C candidates

Best for:
- polities with rich textual descriptions but weak geometry

Weaknesses:
- depends on robust extraction and good named-feature geometry

### Method E — Region occupancy model
Model control at grid-cell level and polygonize only high-confidence cells.

Approach:
- tile the world into analysis cells
- compute features per cell:
  - distance to capital
  - distance to polity settlements
  - route accessibility
  - terrain cost
  - basin / river membership
  - neighboring control at prior time step
  - textual inclusion / exclusion masks
- score each cell for likely control
- polygonize only cells over threshold

Best for:
- scalable global experimentation
- explicit confidence surfaces

Weaknesses:
- depends heavily on feature engineering and threshold choice

## Recommended Experimental Order
Run the methods in this order:

1. **Temporal interpolation**
   - cheapest and most defensible when snapshots exist.
2. **Capital-centered influence fields**
   - good first approximation for missing-state territories.
3. **Region occupancy model**
   - strongest long-term architecture because it produces confidence surfaces.
4. **Text constraint geometry**
   - use as an evidence booster, not as sole generator.
5. **Weighted Voronoi**
   - keep as a baseline comparison method.

## Gap Detection Rules
An inference job should run only when all of the following are true:
- entity type is territory-bearing (`political_entity`, later optionally `cultural_region` or similar)
- target date is known
- no verified geometry snapshot covers the date
- no OHM geometry snapshot covers the date
- minimum evidence bundle threshold is met

Minimum evidence bundle:
- at least one polity anchor (`wikidata_id`, stable identity, name aliases)
- at least one temporal anchor
- at least one geographic anchor (capital, settlement cluster, or textual region)

## Evidence Bundle Schema
Each inference attempt should assemble a normalized evidence bundle:

```json
{
  "entity_id": 123,
  "label": "Neo-Assyrian Empire",
  "target_date": "-0700-01-01",
  "temporal_window": {
    "start": -720,
    "end": -680
  },
  "anchors": {
    "capital_places": [],
    "settlements": [],
    "routes": [],
    "hydrology": [],
    "terrain_barriers": [],
    "text_constraints": []
  },
  "reference_snapshots": {
    "prior": null,
    "next": null
  },
  "source_bundle": ["ohm", "wikidata", "natural_earth", "open_hydro"]
}
```

## Confidence Model
Every candidate polygon needs a confidence score in the range `[0, 1]`.

Suggested weighted score:

$$
C = 0.30T + 0.20A + 0.20G + 0.15X + 0.10V + 0.05S
$$

Where:
- $T$ = temporal support score
- $A$ = anchor quality score
- $G$ = geographic coherence score
- $X$ = cross-method agreement score
- $V$ = topology validity score
- $S$ = source quality score

### Suggested sub-scores
- **Temporal support**
  - high when prior/next snapshots are near in time
  - low when polity chronology is sparse or discontinuous
- **Anchor quality**
  - based on capital certainty, number of settlements, and administrative place coverage
- **Geographic coherence**
  - penalize impossible sea crossings, fragmented enclaves, barrier violations, and detached islands without support
- **Cross-method agreement**
  - reward strong overlap between interpolation, influence, and occupancy results
- **Topology validity**
  - reward valid polygons with acceptable sliver count and compactness
- **Source quality**
  - reward richer evidence from allowed sources with strong provenance

## Publish / Abstain Rules
Suggested thresholds:
- `C >= 0.85` → publish as `inferred_high_confidence`
- `0.70 <= C < 0.85` → store as `inferred_candidate_only`, do not serve by default
- `C < 0.70` → abstain

Additional hard rejection rules:
- invalid geometry after repair
- more than one disconnected mainland component without evidence
- no capital or settlement anchor
- direct contradiction between input methods beyond tolerance
- source registry contains incompatible license flags

## Storage Model
Do not write inferred geometry into the main canonical geometry fields.

Add a dedicated store, for example:
- `inferred_geometry_snapshots`

Suggested fields:
- `id`
- `entity_id`
- `snapshot_date_start`
- `snapshot_date_end`
- `geom`
- `confidence_score`
- `confidence_band`
- `inference_method`
- `model_version`
- `source_bundle`
- `topology_metrics` (JSON)
- `evidence_summary` (JSON)
- `generated_at`
- `invalidated_at` (nullable)

This table should support multiple competing snapshots per entity/date so experiments can be compared before choosing a serving policy.

## Serving Policy
Recommended map-serving policy:
- canonical layers render first
- inferred layers render only when canonical geometry is absent and the snapshot is in the publishable confidence band
- inferred layers use a visibly distinct style:
  - lighter fill
  - dashed outline
  - optional uncertainty hatch pattern
- API returns provenance and confidence so the client can label uncertainty
- inferred overlays should be experimental and off by default in the client until the experiment clears promotion criteria

## Evaluation Without Human Review
Since no review is allowed, evaluation must be statistical and comparative.

### Offline backtesting
Hide known good snapshots, run inference, then compare generated output against the held-out truth.

Metrics:
- IoU / Jaccard overlap
- Hausdorff distance
- centroid error
- boundary length ratio
- component count difference
- topology validity rate
- abstention rate

Recommended initial quantitative targets for a region/time slice to be considered viable:
- median IoU >= 0.60
- p25 IoU >= 0.40
- topology validity rate >= 0.98
- false-positive publish rate <= 0.05
- abstention rate on weak-evidence cases >= 0.50

### Temporal robustness tests
For states with many dated snapshots:
- infer each missing year from neighboring years
- compare degradation as temporal distance increases
- identify safe operating windows for interpolation

### Cross-method agreement
Run multiple methods on the same target and measure overlap.
Low agreement should increase abstention probability.

### Region-specific benchmarking
Benchmark separately by geography and era:
- ancient Mediterranean
- early modern Europe
- steppe polities
- colonial empires
- island archipelagos

The experiment should expect very different failure modes by region.

## Experimental Phases

### Phase 0 — Source registry + gap inventory
Deliverables:
- approved source registry schema
- list of allowed geometry-capable sources
- OHM boundary gap report by polity/date

Exit criteria:
- pipeline can enumerate missing-boundary cases safely
- 100% of enabled sources pass the compliance gate
- unknown-license sources are rejected automatically

### Phase 1 — Baseline interpolation prototype
Deliverables:
- interpolation prototype for entities with adjacent snapshots
- held-out backtest report
- initial confidence score implementation

Exit criteria:
- median IoU >= 0.60 on small-gap benchmarks
- topology validity rate >= 0.98
- no client/API serving yet

### Phase 2 — Influence-field prototype
Deliverables:
- travel-cost / barrier-aware influence engine
- settlement / capital anchor ingestion
- comparison report against Phase 1

Exit criteria:
- method increases benchmark coverage by >= 15% over Phase 1 on no-snapshot cases
- false-positive publish rate remains <= 0.05 in offline tests
- no client/API serving yet

### Phase 3 — Occupancy model prototype
Deliverables:
- grid-cell scoring engine
- feature extraction for terrain, hydrology, anchors, temporal context
- polygonization and confidence surface export

Exit criteria:
- abstention policy is operational and measurable
- low-confidence candidates are stored but not served
- benchmark metrics meet or exceed Phase 2

### Phase 4 — Text constraints + fusion
Deliverables:
- text constraint extraction pipeline
- fusion layer that boosts or suppresses occupancy/influence results
- cross-method agreement scoring

Exit criteria:
- text constraints improve median IoU by >= 0.05 on selected benchmark sets
- contradiction detection reduces false positives relative to Phase 3

### Phase 5 — Serving experiment
Deliverables:
- inferred snapshot storage
- API exposure
- experimental client rendering mode

Exit criteria:
- inferred layers can be rendered without contaminating canonical data
- only `inferred_high_confidence` snapshots are eligible for serving
- inferred overlay remains off by default
- API exposes `is_inferred`, `confidence_band`, and `do_not_merge_canonical`

## Risks
- inferred borders may appear more authoritative than they are
- sparse historical anchors may produce false certainty
- grid-based methods may create ugly or unrealistic frontier artifacts
- evaluation may overfit Europe / literate regions
- automated thresholds may be too permissive or too conservative

## Mitigations
- keep inferred output separate from canonical geometry
- render inferred layers with explicit uncertainty styling
- default to abstain on weak evidence
- maintain region-specific evaluation datasets
- version all models and invalidate outdated generated snapshots cleanly

## Recommended First Slice
The smallest useful experiment is:
1. build a source registry,
2. generate an OHM gap inventory for `political_entity`,
3. prototype temporal interpolation,
4. measure against held-out known snapshots,
5. publish nothing yet — just produce metrics.

If this first slice fails, stop early and avoid building more speculative inference engines.

## Promotion Gate
The experiment should remain non-default until all of the following are true:
1. compliance gate is enforced in code, not just documented
2. only high-confidence inferred snapshots are served
3. serving false-positive rate remains <= 0.05 on benchmarked slices
4. inferred overlays remain visually distinct and non-canonical in the API contract
5. backtest metrics are stable across more than one geography/time slice

## Files Likely Involved in a Future Implementation
Python pipeline:
- `pipeline/config.py`
- `pipeline/scraper/`
- `pipeline/mapper/`
- `pipeline/output/`
- new modules under `pipeline/inference/`

Laravel/API side:
- entity / geometry snapshot models and migrations under `api/app/` and `api/database/`
- map-serving query layer
- inferred-layer API resources

Docs:
- `docs/data_pipeline_architecture.md`
- `docs/entity_specification.md`
- this experimental plan

## Exit Criteria for the Entire Experiment
Proceed beyond experiment status only if:
1. license-safe source policy is fully enforceable,
2. inferred output is clearly non-canonical,
3. backtests show acceptable accuracy for at least one region/time slice,
4. abstention keeps low-confidence output out of the product,
5. serving inferred layers improves coverage without misleading users.

## Status
- Experimental plan only
- No implementation yet
