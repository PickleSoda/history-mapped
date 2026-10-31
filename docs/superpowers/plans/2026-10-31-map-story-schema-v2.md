# Map-story schema v2 — Implementation Plan

> **For agentic workers:** this plan has two parts that run in parallel, each with its own agent. Part P covers the pipeline, the API and the guide; Part W covers the web renderer. Steps use checkbox (`- [ ]`) syntax.

**Goal:** implement the v2 contract in `docs/superpowers/specs/2026-10-31-map-story-schema-v2-design.md` end to end. Upgrade the five sample battles so each new feature is used at least once where the history supports it.

**Contract:** the spec is the source of truth for field names, enums and semantics. Don't rename or extend anything in it without asking. If something is impossible or ambiguous, choose the least surprising reading, note it in your report, and keep both sides consistent.

## Ground rules (both parts)

- **Shared checkout.** Work in `/home/pickle/code/history-mapped`. Other agents are editing other files at the same time.
  - Edit only the files your part owns (listed below). If you need a change in a file you don't own, describe it in your report; don't make it.
  - Don't commit, and don't run git commands that change state (stash, checkout, reset, restore). `git diff` and `git status` are fine.
  - `web/src/components/map/MapCanvas.tsx` belongs to a peer session working in another worktree. Avoid it. If you can't, keep the change to a few lines and report it.
- **Never run PHP on the host.**
  - PHP and artisan: `docker compose -f docker/docker-compose.yml exec -T app php artisan test --filter MapStory`.
  - Formatting: `docker compose -f docker/docker-compose.yml exec -T app vendor/bin/pint <your files>`. Pass file paths; never use `--dirty`, which reformats other agents' files.
- **Python:**
  - Tests: `scripts/capped.sh pipeline/.venv/bin/python3 -m pytest pipeline/tests/test_map_stories.py -q`.
  - Build and check stories: `scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.map_stories build|check|preview …`.
- **Web**, from the repo root:
  ```bash
  docker compose -f docker/docker-compose.yml run --rm --no-deps --entrypoint '' web sh -c 'cd /workspace/web 2>/dev/null || cd web; pnpm exec vitest run'
  ```
  Use the same pattern for `pnpm exec tsc --noEmit`, `pnpm exec eslint src` and `pnpm exec vite build`.
- **Style:** match the surrounding code, including its comment density, naming and idioms.
  - PHP: `declare(strict_types=1)`, final classes, typed.
  - TS: zod-first, pure functions in `lib/`.
  - Python: typed, small functions.

---

## Part P — pipeline, API, samples, guide

**Owns:**
- `pipeline/map_stories/schema.py`, `validate.py`, `geo.py`
- `pipeline/map_stories/stories/*.py`
- `api/resources/map-stories/*.json`, the build output
- `pipeline/tests/test_map_stories.py`
- `api/app/Support/MapStory/*`
- `api/tests/**/MapStory*` (existing and new)
- `docs/implementation-docs/map-story-authoring.md`

**Does not own:** `pipeline/map_stories/__main__.py`, `preview.py`, and any new pipeline module. Those belong to the bulk-run-readiness agent. `resolve_steps(doc)` must keep its signature and return shape, because `preview.py` imports it.

- [ ] **P1. Vocabulary.** Add the new enums and kinds to `schema.py` and `MapStoryVocabulary.php`, and set `SCHEMA_VERSION = 2`:
  - unit kinds `standard` and `ship`, both point kinds;
  - unit states `killed`, `wounded`, `captured`, `sunk`, `aground`, `burning`;
  - move types `ram`, `back_water`, `blockade`, `landing`;
  - `TERRAIN_STATES`, `LIGHTS`, the terrain kind `mask` (area).

  Keep the two files in lockstep, and update the "mirrors" docblocks.
- [ ] **P2. Python validator.**
  - **Schema field.** Accept `schema` 1 or 2. When a v1 document uses a v2 field, report an error telling the author to bump `schema`.
  - **Field validation.** Validate every v2 field: types, ranges, references to unit/side/terrain/contingent ids, and `by` required with `captured`.
  - **Beats.** Add `resolve_beats(doc, i)`, and make `resolve_steps` honour beats (the frame after the last beat), `from`/`into`, and `terrain_state` carry-forward. The `terrain_state` carry-forward can be a separate `resolve_terrain_state(doc)`.
  - **Teleport and spread checks.** Run the teleport check per beat. Skip `frame: false` placements in the spread checks. `from` units start at their parent's position.
  - **State/kind fit.** Warn when a state doesn't fit the unit's kind.
  - **Land/water check.** Do the land/water check from §7 with a shapely-free point-in-polygon (`geo.py` may gain `point_in_ring` and `distance_to_line`).
  - **Limits.** Raise the `uncertainty` limit to 1500.
- [ ] **P3. Python tests.** For each feature group (1–7 and extras), test one valid document and one invalid document. Also test `resolve_beats` and the `from`/`into` resolution. Keep the parametrised committed-stories test.
- [ ] **P4. API validator.** Port the same structural checks to `MapStoryDocument::errors()`; warnings stay in Python. Q-id resolution for `sides[].contingents` isn't needed.
  - Feature tests: a v2 document syncs; a v1 document that uses a v2 field is rejected with a clear message; the beats, `terrain_state` and contingent references are checked.
  - Run the whole MapStory test filter plus `EntityResource` tests.
- [ ] **P5. Upgrade the samples.** Edit the builders in `pipeline/map_stories/stories/`, rebuild them, and set `schema: 2`. Use a feature only where the sources support it:
  - **Cannae:** `lines: 3` for the Roman infantry (triplex acies); `sun`/`wind` (the Volturnus wind and dust toward the Romans, per Livy); `killed` for Aemilius Paullus at the end; `conjectural` on the disputed river bank, plus `alt_sites` for the left- and right-bank theories; a beat for the centre's withdrawal, then the envelopment.
  - **Gaugamela:** `contingents` for the Persian satrapies and Alexander's allies; `lanes` in the Macedonian line opened for the scythed chariots; a `standard` if attested; `captured` for the Persian baggage/camp (by Mazaeus's raid, if supported).
  - **Salamis:** `orient: "path"` on the fleet moves; `ram`, `sunk` and `back_water`; `light: night` → `dawn` at the start; a `ship` marker for Artemisia's or Xerxes' vantage only if it fits; the land/water check must pass.
  - **Hastings:** `beats` for the feigned flights (flee, then wheel on the pursuers); `killed` for Harold; a `standard` (the Wessex dragon / the Fighting Man).
  - **Waterloo:**
    - `terrain_state` for Hougoumont, La Haye Sainte and Plancenoit (held_by, burning, captured, contested);
    - `subunits` squares against Ney's cavalry;
    - `contingents` (British, KGL/Hanoverian, Dutch-Belgian, Brunswick, Nassau);
    - `frame: false` plus `continues` for the Prussian approach from Wavre;
    - `light: dusk` at the end;
    - `fire` with `target` for the grand battery.

  Run `check` on every story. A rebuilt story must have no errors and no new warnings.
- [ ] **P6. Guide.** Document every v2 field in `map-story-authoring.md`, with a short example for each and a "when to use" line. Mark the v2 fields as v2. Keep the guide compact: the bulk Sonnet authors read it, and every extra line costs tokens across hundreds of runs. Put any long reference material at the end.
- [ ] **P7. Sync and verify.** Run `docker compose … exec -T app php artisan map-stories:sync --force`, then run the full Python and MapStory PHP suites and Pint on your PHP files.

**Report** in at most 15 lines: files changed, test counts, which sample uses which feature, anything you couldn't express, and any change you need in files you don't own.

---

## Part W — web renderer

**Owns:**
- `web/src/lib/schemas/map-story.ts`
- `web/src/lib/map-story/*`, including tests
- `web/src/components/map/StoryOverlay.tsx`
- `web/src/components/atlas/StoryPlayer.tsx`, `StoryCard.tsx`
- New components under `web/src/components/map/` or `components/atlas/` whose names start with `Story`
- The "Battle maps" section of `docs/architecture/frontend-app.md`

- [ ] **W1. Zod schema.** Add every v2 field from the spec, tolerant as today: unknown enums `.catch` to the v1 default.
- [ ] **W2. `geometry.ts`.**
  - **Resolution:** extend `resolveFrames` (beats, `from`/`into`, the hidden-after-merge rule) and add `resolveBeats(doc, i)` and `resolveTerrainState(doc)`.
  - **Formations:** `formation()` supports `lines`, `lanes` and `subunits`, including checkerboard and squares, and returns several rings when needed.
  - **Tweening:** `tween` supports `orient: "path"` and `from`/`into` (start at, or end at, the other unit).
  - **Framing:** `stepBounds` ignores `frame: false` placements, `continues` tails and `alt_sites`.
  - **Tests:** add vitest coverage for each of these.
- [ ] **W3. `icons.ts`.**
  - Glyphs for `standard` (a flag) and `ship` (one hull).
  - State overlays for killed, wounded, captured, sunk, aground and burning.
  - Terrain-state glyphs: flames, crossed swords, captured flag.
  - Move heads for ram and landing, and blockade ticks.
  - Keep everything drawn on canvas and registered per side colour, as today.
- [ ] **W4. `layers.ts`.**
  - **Composite units:** rank bands for `ranks`.
  - **Contingents:** a contingent colour or an automatic shade. Derive the shade deterministically, for example by mixing the side colour with white or black by index.
  - **Conjectural:** dashed and light styling for `conjectural` on placements, moves, terrain and notes.
  - **Off-map tails:** `continues` tails with edge labels.
  - **Fire:** `fire` `target` and `arc` (a quadratic bezier).
  - **Terrain state:** fill or outline held features in the holder's colour, plus the glyph.
  - **Mask:** the `mask` terrain hides the modern reference layers inside it.
  - **Alt sites:** `alt_sites` ghost pins.
  - **Light:** a tint, done as a full-screen fill layer or a CSS overlay, whichever stays performant.
- [ ] **W5. `StoryOverlay.tsx`.**
  - **Beat playback:** a forward step plays the step's tween, then each beat (about 1.2 s each) with a caption. A jump or a backward step lands on the final frame. Reduced motion lands immediately.
  - **Off-screen indicator:** edge chevrons for units outside the viewport, recomputed on move. A small absolutely positioned DOM layer rendered from StoryOverlay is fine.
  - **HUD:** the wind/sun HUD.
  - **Tooltips:** the hover card shows the contingent, `strength_n` and the state.
- [ ] **W6. `StoryPlayer.tsx`.**
  - "About this reconstruction" lists `alt_sites` and adds the line "dashed = conjectural" when the document uses `conjectural`.
  - Beat captions also appear in the step text, as a small sub-list, when a step has beats.
- [ ] **W7. Verify in the browser.**
  - Run vitest, tsc, eslint (0 errors) and vite build.
  - Part P upgrades the samples in parallel, so their JSON may not use v2 yet when you test. Verify with a local fixture first: a temporary v2 story file in `api/resources/map-stories/zz-v2-fixture.json`, synced with `php artisan map-stories:sync --slug=zz-v2-fixture`.
    - If the API validator rejects v2 because Part P hasn't landed it yet, insert the row directly with psql instead (`docker compose -f docker/docker-compose.yml exec -T db psql -U history-mapped history-mapped`). Copy the columns of an existing `map_stories` row.
    - Before you finish, delete the fixture file and its row.
  - Then load the five real stories at `http://localhost:5173/?story=battle-of-<name>` once Part P's JSON is synced. Use the claude-in-chrome tools: create your own tab, and screenshot at most about 12 frames in total.

**Report** in at most 15 lines: files changed, test counts, what you verified in the browser, and any deviation from the spec.
