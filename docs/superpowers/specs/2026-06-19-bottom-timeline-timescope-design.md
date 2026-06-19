# Bottom timeline — timescope gantt + scrubber

**Date:** 2026-06-19
**Status:** Approved (design); pending implementation plan
**Surface:** `web/` (public Atlas SPA, React 19 + Vite)
**Related:** [`2026-06-13-atlas-frontend-plumbing-design.md`](2026-06-13-atlas-frontend-plumbing-design.md) (time-state / ephemeral plumbing), [`2026-06-19-mobile-responsive-drawer-design.md`](2026-06-19-mobile-responsive-drawer-design.md) (shares the bottom-spine slot)

## Problem

The Atlas bottom spine ([`web/src/components/atlas/Timeline.tsx`](../../../web/src/components/atlas/Timeline.tsx), 56px) renders era bands, tick marks, and a scrubber handle, but **has no interactivity** — you cannot drag to change the year, and it shows no per-entity temporal context. Time is changed only by the TopBar ±10yr buttons. We want a richer, interactive bottom timeline and a way to visualise entity lifespans (a gantt), and to evaluate the `timescope` canvas library for this.

## Goals

- Replace the bottom spine with a `timescope`-based component that is **a working time scrubber** (drag the playhead to set the current year; the map reacts).
- Render entity lifespans as a **gantt** (horizontal `box` spans in lanes) — using **sample data** for this first version.
- Make the bar **collapsible**: a compact scrubber by default, an expanded gantt on demand.
- Add a **Vitest** setup to `web/` and unit-test the pure helpers test-first.
- Preserve all current behaviour: no regression to the existing time→map wiring.

## Non-goals (deferred to later increments)

- Real entity-span data (a `/entities/map` time-window query, or a new timeline endpoint + the deferred `useTimelineDensity`/`useHighlights` hooks). v1 uses sample data only.
- Range selection (`?t=start..end`) driven from the timeline, even though `timescope` supports it.
- Play / animate-through-time.
- Persisting zoom or collapse state to URL / localStorage.
- Any backend (Laravel) changes. (Also impractical from this worktree — the Docker stack mounts the main checkout's `api/`.)

## Decisions (locked with stakeholder)

1. **Role:** timescope **replaces** `Timeline.tsx` and doubles as the scrubber (one unified component).
2. **Data:** **sample** gantt data for v1; real data is a clean follow-up at the `sampleSpans` seam.
3. **Playhead:** **fully wired** — drag updates live state and commits to the URL on release; the map reacts.
4. **Collapsible:** compact scrubber ↔ expanded gantt; state in the ephemeral store.
5. **Integration:** the official **`@timescope/react`** wrapper (approach A), not a hand-rolled imperative wrap.
6. **Testing:** add **Vitest** to `web/`; TDD the pure helpers; the canvas component is verified visually.

## Dependencies

Add to `web/`:

| Package | Version | Notes |
|---------|---------|-------|
| `@timescope/react` | `0.0.0-alpha.11` | React 19 wrapper. Peer: `react@^19.2.3` (we have 19.2.4 ✓). |
| `timescope` | `^0.0.0-alpha.11` | core (transitive, but pin explicitly). |
| `@kikuchan/decimal` | `0.1.0-alpha.5` | **exact** — `@timescope/react` peer pins this version (latest is alpha.8). |
| `vitest` (+ `jsdom`, `@vitest/...`) | latest | dev-only, for the helper tests. |

**Risk:** all three runtime deps are `0.0.0-alpha` — the API may shift. Acceptable for an evaluation in an isolated worktree; isolated behind our adapter so churn is contained to one component + two pure modules.

## `@timescope/react` API (verified from the shipped `.d.ts`)

Controlled component. Relevant props/events:

- `time?: number | Decimal | string | Date | null` — the **playhead** position. Numeric, negatives allowed → BCE works.
- `indicator?: boolean` — draws the playhead/cursor line.
- `zoom?`, `zoomRange?`, `timeRange?` — viewport controls.
- `sources` / `series` / `tracks` — data + marks (`box`, `text`, …) + lanes.
- `onTimeChanging(v: Decimal|null)` — fires **during** drag → live scrub.
- `onTimeChanged(v: Decimal|null)` — fires on **release** → commit.
- `onZoomChanged(n)` / `onZoomChanging(n)`; `onSelectedRange*` (range select; deferred).
- Imperative ref `TimescopeAPI`: `setTime`, `setZoom`, `fitTo`.

Callback values are `@kikuchan/decimal` `Decimal` (or `null`); convert with `Number(v)` and guard null.

## Architecture

One new presentational component plus two pure modules. The component is a thin **adapter** between the app's time state and `<Timescope />`; it holds no domain logic.

```
web/src/
  components/atlas/
    TimelineScope.tsx        # NEW — adapter; swapped into AtlasLayout's bottom slot
    Timeline.tsx             # kept until parity confirmed, then removed
  lib/timeline/
    sampleSpans.ts           # NEW — pure: sample sources/series/tracks, themed
    year.ts                  # NEW — pure: Decimal→year conversion + clamp/round
    sampleSpans.test.ts      # NEW — Vitest
    year.test.ts             # NEW — Vitest
  stores/ephemeral.ts        # +timelineExpanded + setTimelineExpanded
  app/routes/AtlasLayout.tsx # swap <Timeline/> → <TimelineScope/>
web/vitest.config.ts         # NEW
```

**Component boundaries:**

- **`TimelineScope.tsx`** — reads the current year via `useTimeState` (`instantYear()`), reads `timelineExpanded` from the ephemeral store, renders `<Timescope />` with sample data + the three wired callbacks + a chevron toggle + a year/era readout. Reuses [`web/src/lib/format.ts`](../../../web/src/lib/format.ts) for display: `formatTime`/`eraFor` for the readout and `formatYear` as the timescope time-axis label formatter. *Depends on:* store hooks, `sampleSpans`, `year`, `lib/format`.
- **`lib/timeline/sampleSpans.ts`** — returns the `{ sources, series, tracks }` for the sample gantt, with span colours mapped to the five entity-group hexes. **This is the seam** where real data later replaces sample data. *Depends on:* nothing.
- **`lib/timeline/year.ts`** — only the timescope-specific conversion the existing utils don't cover: `toYear(v: Decimal|number|null): number | null` (unwrap `Decimal` → number, null-safe) and `roundYear`/clamp. BCE/CE *formatting* is **not** duplicated here — it reuses `formatYear` from `lib/format.ts`. *Depends on:* nothing.

## Data flow

```
useTimeState (URL ?t)  ──instantYear()──▶  <Timescope time={year} indicator>
        ▲                                          │
        │ onTimeChanged (release)                  │ onTimeChanging (drag)
   setInstant(roundYear(Number(v)))           setLiveScrub(Number(v)) ──▶ ephemeral
        │                                          (timeline visual feedback only)
        ▼
   URL ?t updates ──▶ MapCanvas time effect ──▶ map re-filters   ✓ already wired
```

On **release** the URL changes and the existing `MapCanvas` time effect re-filters the map (no new map wiring). During **drag** only the ephemeral `liveScrub` updates, so the URL/map are not thrashed per frame.

## Collapsible behaviour

- State: `timelineExpanded: boolean` in [`web/src/stores/ephemeral.ts`](../../../web/src/stores/ephemeral.ts) (UI-interaction state; resets on refresh — consistent with `hoverId`, `liveScrub`, etc.). A `useTimelineExpanded()` hook mirrors the existing ephemeral hooks.
- **Collapsed (~56px, default):** short `<Timescope />` — time axis + playhead + year/era readout; lanes/spans suppressed. Behaviourally equals the old scrubber.
- **Expanded (~170px):** full gantt — `box` spans in lanes + `text` labels + the same playhead.
- A chevron button toggles the state. Height transitions via the existing `flex-none border-t bg-card` slot.

## Interaction details

- **Drag playhead:** as in Data flow (live → commit). Works in both states.
- **Zoom:** timescope's built-in wheel zoom; `zoom` held in local component state with a sensible default window; `onZoomChanged` updates it. Not persisted.
- **Dropped from the old bar:** the unwired era-band strip and the static play/zoom buttons. **Kept:** the current-year + era-label readout (reusing `formatTime` + `eraFor` from [`web/src/lib/format.ts`](../../../web/src/lib/format.ts), exactly as the old `Timeline.tsx` does).

## Theming

- Span colours: a small TS token map mirroring the five `--g-*` entity-group hexes in [`web/src/styles.css`](../../../web/src/styles.css) (they do not change in dark mode, so static hex is safe). timescope style options accept colour strings / data-functions.
- Canvas `background`: read `--card` (or `--background`) from `getComputedStyle(document.documentElement)` so it fits light/dark.
- Fonts: default; optionally pass Geist later.

## Testing

- **Vitest** added to `web/` (`vitest`, `jsdom`, `vitest.config.ts`; a `test` script in `web/package.json`).
- **TDD, pure helpers:**
  - `year.test.ts` — `toYear` (unwraps `Decimal`, passes through `number`, null-safe) and `roundYear` clamping. (BCE/CE formatting is the existing `formatYear`; add a couple of boundary cases to `format.ts` coverage only if it lacks them — incl. year 0 / 1 BCE.)
  - `sampleSpans.test.ts` — returns the expected sources/series/tracks shape; every span maps to a known group colour; lanes within `tracks` range.
- **`TimelineScope.tsx`** — verified **visually** in the running SPA (canvas rendering is not meaningfully unit-testable in jsdom). Manual checks: collapsed/expanded toggle; drag playhead moves the year readout and, on release, pans the map; BCE/CE axis labels correct.
- **Gates:** `pnpm --filter @history-mapped/web types:check`, `pnpm --filter @history-mapped/web lint`, `pnpm --filter @history-mapped/web test`.

## Risks & mitigations

- **Alpha API churn** → isolate behind `TimelineScope` + pure modules; pin `@kikuchan/decimal` exactly; fall back to wrapping the imperative `timescope` core (approach B) if the wrapper fights React's render cycle.
- **timescope axis assumes calendar time** → supply a custom historical-year formatter via the time-axis options; treat the numeric domain as plain years.
- **Replacing `Timeline.tsx`** → keep the old file until parity is visually confirmed, then remove; run GitNexus `impact` on the `Timeline` symbol before deletion (per repo CLAUDE.md).
- **Worktree ≠ Docker mount** → v1 is frontend-only with sample data, so it runs fully via host-side Vite; no backend dependency.

## Out-of-scope follow-ups (natural next steps)

1. Real spans from `/entities/map` queried over the timeline's visible **window** (uses `start_year`/`end_year` already on map features; no backend change).
2. A dedicated timeline/density endpoint + enable `useTimelineDensity()` / `useHighlights()`.
3. Range selection → `setRange` (`?t=a..b`); play/animate; persisted zoom & collapse.
