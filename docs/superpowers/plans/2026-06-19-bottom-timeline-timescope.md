# Bottom Timeline (timescope) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static bottom `Timeline.tsx` with a collapsible `timescope` component that shows a sample entity-lifespan gantt and a fully-wired draggable playhead bound to the app's time state.

**Architecture:** A thin React adapter (`TimelineScope.tsx`) renders the `@timescope/react` controlled component. Its `time` prop is driven by `useTimeState`; `onTimeChanging` feeds the ephemeral live-scrub for a live readout and `onTimeChanged` commits the year to the URL on release, which the existing `MapCanvas` time effect already reacts to. Gantt data is sample-only in this increment, isolated in a pure module so real data can replace it later. Pure helpers are unit-tested with a new Vitest setup; the canvas component is verified visually.

**Tech Stack:** React 19, Vite, TypeScript (strict), Zustand, nuqs, `@timescope/react` (alpha), Vitest.

## Global Constraints

- Work in `web/` only. Run scripts from the repo root as `pnpm --filter @history-mapped/web <script>` (or `pnpm <script>` inside `web/`). No backend (Laravel) changes.
- Dependencies (exact / floor as written): `@timescope/react@0.0.0-alpha.11`, `timescope@0.0.0-alpha.11`, `@kikuchan/decimal@0.1.0-alpha.5` (EXACT — `@timescope/react`'s peer pins this version). Dev: `vitest`, `jsdom`.
- React is 19.2.4, which satisfies `@timescope/react`'s `react@^19.2.3` peer. Do not downgrade.
- Reuse `web/src/lib/format.ts` — `formatYear`, `formatTime`, `eraFor`, `instantYear`. Do NOT duplicate year/era formatting.
- Entity-group colours differ between light and dark themes and canvas cannot resolve `var(--…)`. Resolve hex at runtime with `getComputedStyle(...).getPropertyValue('--g-<group>')` + literal fallback (mirror of `web/src/lib/map-icons.ts`).
- Ephemeral store rule: read with slice selectors only (`useEphemeralStore(s => s.x)`); expose via hooks in `web/src/hooks/ephemeral.ts`; re-export from `web/src/hooks/index.ts`.
- TypeScript is strict with `noUnusedLocals`/`noUnusedParameters`; path alias `@/* → src/*`.
- TDD for pure logic. Commit after each task. Conventional commit messages.
- Each task ends green: `pnpm --filter @history-mapped/web test`, `… types:check`, and `… lint` must pass.

---

### Task 1: Vitest setup + `year.ts` (Decimal→year conversion)

**Files:**
- Modify: `web/package.json` (devDeps + `test` script)
- Create: `web/vitest.config.ts`
- Create: `web/src/lib/timeline/year.ts`
- Test: `web/src/lib/timeline/year.test.ts`

**Interfaces:**
- Produces: `toYear(v: DecimalLike | number | null): number | null` and `clampYear(year: number, min?: number, max?: number): number`; constants `AXIS_MIN = -4000`, `AXIS_MAX = 2025`; exported `type DecimalLike = { number(): number }`.

- [ ] **Step 1: Install Vitest + jsdom (dev)**

Run: `pnpm --filter @history-mapped/web add -D vitest jsdom`
Expected: both appear under `devDependencies` in `web/package.json`.

- [ ] **Step 2: Add the `test` script to `web/package.json`**

In the `"scripts"` block, add (keep existing entries):

```json
    "test": "vitest run",
    "test:watch": "vitest"
```

- [ ] **Step 3: Create `web/vitest.config.ts`**

```ts
import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts'],
  },
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
});
```

- [ ] **Step 4: Write the failing test** — `web/src/lib/timeline/year.test.ts`

```ts
import { describe, it, expect } from 'vitest';
import { toYear, clampYear, AXIS_MIN, AXIS_MAX } from './year';

describe('toYear', () => {
  it('passes through an integer year', () => expect(toYear(753)).toBe(753));
  it('passes through a negative (BCE) year', () => expect(toYear(-753)).toBe(-753));
  it('rounds a fractional value', () => expect(toYear(-489.6)).toBe(-490));
  it('returns null for null', () => expect(toYear(null)).toBeNull());
  it('unwraps a Decimal-like via .number()', () =>
    expect(toYear({ number: () => -321.4 })).toBe(-321));
});

describe('clampYear', () => {
  it('clamps below the floor', () => expect(clampYear(-99999)).toBe(AXIS_MIN));
  it('clamps above the ceiling', () => expect(clampYear(99999)).toBe(AXIS_MAX));
  it('passes a year inside the window', () => expect(clampYear(476)).toBe(476));
});
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `pnpm --filter @history-mapped/web test`
Expected: FAIL — cannot resolve `./year`.

- [ ] **Step 6: Implement `web/src/lib/timeline/year.ts`**

```ts
/**
 * timescope-specific year conversion. The timeline domain is plain historical
 * years (negative = BCE); timescope callbacks hand back `@kikuchan/decimal`
 * values whose `.number()` is that same year. BCE/CE *formatting* is NOT here —
 * use `formatYear` from `@/lib/format`.
 */

/** Minimal shape of the decimal value timescope passes to time callbacks. */
export type DecimalLike = { number(): number };

/** Supported timeline axis window. */
export const AXIS_MIN = -4000;
export const AXIS_MAX = 2025;

/** A timescope time value (Decimal | number | null) → an integer year or null. */
export function toYear(v: DecimalLike | number | null): number | null {
  if (v == null) return null;
  const n = typeof v === 'number' ? v : v.number();
  return Number.isFinite(n) ? Math.round(n) : null;
}

/** Clamp a year into the supported axis window. */
export function clampYear(year: number, min = AXIS_MIN, max = AXIS_MAX): number {
  return Math.max(min, Math.min(max, year));
}
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `pnpm --filter @history-mapped/web test`
Expected: PASS (8 tests).

- [ ] **Step 8: Commit**

```bash
git add web/package.json web/pnpm-lock.yaml ../pnpm-lock.yaml web/vitest.config.ts web/src/lib/timeline/year.ts web/src/lib/timeline/year.test.ts
git commit -m "test(web): add Vitest + timeline year-conversion helper"
```

(If `git add` reports a path that does not exist, drop it — the workspace lockfile may live only at the repo root.)

---

### Task 2: `colors.ts` + `sampleSpans.ts` (themed sample gantt data)

**Files:**
- Create: `web/src/lib/timeline/colors.ts`
- Create: `web/src/lib/timeline/sampleSpans.ts`
- Test: `web/src/lib/timeline/colors.test.ts`
- Test: `web/src/lib/timeline/sampleSpans.test.ts`

**Interfaces:**
- Consumes: `EntityGroup`, `ENTITY_GROUPS` from `@/types/atlas`.
- Produces: `groupColor(group: EntityGroup): string`; `interface SampleSpan { id: string; label: string; group: EntityGroup; start: number; end: number; lane: number }`; `sampleSpans: SampleSpan[]`; `SAMPLE_LANES: number`.

- [ ] **Step 1: Write the failing colours test** — `web/src/lib/timeline/colors.test.ts`

```ts
import { describe, it, expect } from 'vitest';
import { groupColor } from './colors';
import { ENTITY_GROUPS } from '@/types/atlas';

describe('groupColor', () => {
  it('returns a hex fallback for every group when the CSS var is unset (jsdom)', () => {
    for (const g of ENTITY_GROUPS) {
      expect(groupColor(g)).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });
});
```

- [ ] **Step 2: Write the failing sample-data test** — `web/src/lib/timeline/sampleSpans.test.ts`

```ts
import { describe, it, expect } from 'vitest';
import { sampleSpans, SAMPLE_LANES } from './sampleSpans';
import { ENTITY_GROUPS } from '@/types/atlas';

describe('sampleSpans', () => {
  it('is non-empty', () => expect(sampleSpans.length).toBeGreaterThan(0));
  it('every span uses a known entity group', () => {
    for (const s of sampleSpans) expect(ENTITY_GROUPS).toContain(s.group);
  });
  it('every span starts before it ends', () => {
    for (const s of sampleSpans) expect(s.start).toBeLessThan(s.end);
  });
  it('every lane is within [0, SAMPLE_LANES)', () => {
    for (const s of sampleSpans) {
      expect(s.lane).toBeGreaterThanOrEqual(0);
      expect(s.lane).toBeLessThan(SAMPLE_LANES);
    }
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pnpm --filter @history-mapped/web test`
Expected: FAIL — cannot resolve `./colors` and `./sampleSpans`.

- [ ] **Step 4: Implement `web/src/lib/timeline/colors.ts`**

```ts
import type { EntityGroup } from '@/types/atlas';

/** Literal-hex fallbacks (light theme), used when the CSS var is unavailable. */
const FALLBACK: Record<EntityGroup, string> = {
  polity: '#b4543f',
  place: '#2f7d6b',
  event: '#b07d23',
  economy: '#3f6db4',
  culture: '#7a57ad',
};

/**
 * Resolve the active theme's hex for an entity group. Canvas cannot read
 * `var(--…)`, so we read the computed custom property (mirrors map-icons).
 */
export function groupColor(group: EntityGroup): string {
  const v = getComputedStyle(document.documentElement)
    .getPropertyValue(`--g-${group}`)
    .trim();
  return v || FALLBACK[group];
}
```

- [ ] **Step 5: Implement `web/src/lib/timeline/sampleSpans.ts`**

```ts
import type { EntityGroup } from '@/types/atlas';

export interface SampleSpan {
  id: string;
  label: string;
  group: EntityGroup;
  /** Historical year; negative = BCE. */
  start: number;
  end: number;
  /** Lane (row) index, 0-based. */
  lane: number;
}

/** Number of lanes the sample gantt is laid out across. */
export const SAMPLE_LANES = 6;

/** Placeholder gantt until real entity spans are wired (design §"seam"). */
export const sampleSpans: SampleSpan[] = [
  { id: 'rome-rep', label: 'Roman Republic', group: 'polity', start: -509, end: -27, lane: 0 },
  { id: 'rome-emp', label: 'Roman Empire', group: 'polity', start: -27, end: 476, lane: 0 },
  { id: 'han', label: 'Han Dynasty', group: 'polity', start: -206, end: 220, lane: 1 },
  { id: 'maurya', label: 'Maurya Empire', group: 'polity', start: -322, end: -185, lane: 2 },
  { id: 'silk-road', label: 'Silk Road trade', group: 'economy', start: -130, end: 1453, lane: 3 },
  { id: 'library-alex', label: 'Library of Alexandria', group: 'culture', start: -283, end: 275, lane: 4 },
  { id: 'punic-wars', label: 'Punic Wars', group: 'event', start: -264, end: -146, lane: 5 },
  { id: 'alexandria', label: 'Alexandria founded', group: 'place', start: -331, end: -330, lane: 4 },
  { id: 'gupta', label: 'Gupta Empire', group: 'polity', start: 320, end: 550, lane: 2 },
  { id: 'pax-romana', label: 'Pax Romana', group: 'event', start: -27, end: 180, lane: 5 },
];
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pnpm --filter @history-mapped/web test`
Expected: PASS (all timeline tests green).

- [ ] **Step 7: Commit**

```bash
git add web/src/lib/timeline/colors.ts web/src/lib/timeline/colors.test.ts web/src/lib/timeline/sampleSpans.ts web/src/lib/timeline/sampleSpans.test.ts
git commit -m "feat(web): themed sample gantt data + group-colour resolver"
```

---

### Task 3: Collapse state (ephemeral store + hook)

**Files:**
- Modify: `web/src/stores/ephemeral.ts` (add field + setter)
- Modify: `web/src/hooks/ephemeral.ts` (add `useTimelineExpanded`)
- Modify: `web/src/hooks/index.ts` (export `useTimelineExpanded`)
- Test: `web/src/stores/ephemeral.test.ts`

**Interfaces:**
- Produces: store slice `timelineExpanded: boolean` (default `false`) + `setTimelineExpanded(v: boolean)`; hook `useTimelineExpanded(): { expanded: boolean; setExpanded: (v: boolean) => void; toggle: () => void }`.

- [ ] **Step 1: Write the failing store test** — `web/src/stores/ephemeral.test.ts`

```ts
import { describe, it, expect, afterEach } from 'vitest';
import { useEphemeralStore } from './ephemeral';

afterEach(() => useEphemeralStore.getState().setTimelineExpanded(false));

describe('timelineExpanded slice', () => {
  it('defaults to false', () => {
    expect(useEphemeralStore.getState().timelineExpanded).toBe(false);
  });
  it('is updated by setTimelineExpanded', () => {
    useEphemeralStore.getState().setTimelineExpanded(true);
    expect(useEphemeralStore.getState().timelineExpanded).toBe(true);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm --filter @history-mapped/web test`
Expected: FAIL — `timelineExpanded`/`setTimelineExpanded` are not on the store.

- [ ] **Step 3: Add the slice to `web/src/stores/ephemeral.ts`**

In `interface EphemeralState`, after the `map` field add:

```ts
  /** Bottom timeline expanded (gantt) vs collapsed (scrubber). */
  timelineExpanded: boolean;
```

and after `setMap`:

```ts
  setTimelineExpanded: (expanded: boolean) => void;
```

In `create<EphemeralState>()`, after `map: null,` add:

```ts
  timelineExpanded: false,
```

and after `setMap: (map) => set({ map }),` add:

```ts
  setTimelineExpanded: (timelineExpanded) => set({ timelineExpanded }),
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm --filter @history-mapped/web test`
Expected: PASS.

- [ ] **Step 5: Add the hook to `web/src/hooks/ephemeral.ts`**

Append:

```ts
/** Bottom-timeline expanded/collapsed state (gantt vs scrubber). */
export function useTimelineExpanded() {
  const expanded = useEphemeralStore((s) => s.timelineExpanded);
  const setExpanded = useEphemeralStore((s) => s.setTimelineExpanded);
  const toggle = useCallback(() => setExpanded(!expanded), [expanded, setExpanded]);
  return { expanded, setExpanded, toggle };
}
```

- [ ] **Step 6: Export it from `web/src/hooks/index.ts`**

In the ephemeral export block, add `useTimelineExpanded`:

```ts
export {
  useMapInstance,
  useLiveScrub,
  useHover,
  useSheet,
  useCommandPalette,
  useTimelineExpanded,
} from './ephemeral';
```

- [ ] **Step 7: Verify types + tests**

Run: `pnpm --filter @history-mapped/web types:check && pnpm --filter @history-mapped/web test`
Expected: both PASS.

- [ ] **Step 8: Commit**

```bash
git add web/src/stores/ephemeral.ts web/src/stores/ephemeral.test.ts web/src/hooks/ephemeral.ts web/src/hooks/index.ts
git commit -m "feat(web): ephemeral timelineExpanded state + useTimelineExpanded hook"
```

---

### Task 4: Install timescope; baseline `TimelineScope` gantt; swap into layout

**Files:**
- Modify: `web/package.json` (runtime deps)
- Create: `web/src/components/atlas/TimelineScope.tsx`
- Modify: `web/src/app/routes/AtlasLayout.tsx:5` (import) and `:40-43` (slot)

**Interfaces:**
- Consumes: `useTimeState` (`@/hooks`), `instantYear`/`formatYear`/`formatTime`/`eraFor` (`@/lib/format`), `groupColor` (`@/lib/timeline/colors`), `sampleSpans`/`SAMPLE_LANES` (`@/lib/timeline/sampleSpans`).
- Produces: `TimelineScope` React component (read-only playhead at this task; wired in Task 5).

- [ ] **Step 1: Install timescope packages**

Run: `pnpm --filter @history-mapped/web add @timescope/react@0.0.0-alpha.11 timescope@0.0.0-alpha.11 @kikuchan/decimal@0.1.0-alpha.5`
Expected: all three in `web/package.json` `dependencies` at the exact versions. (Ignore the alpha "Ignored build scripts" notice.)

- [ ] **Step 2: Create `web/src/components/atlas/TimelineScope.tsx`** (baseline, read-only playhead)

```tsx
import { Timescope } from '@timescope/react';
import { useTimeState } from '@/hooks';
import { eraFor, formatTime, formatYear, instantYear } from '@/lib/format';
import { groupColor } from '@/lib/timeline/colors';
import { sampleSpans, SAMPLE_LANES } from '@/lib/timeline/sampleSpans';

const TRACK = 'main';

/**
 * Bottom timeline (design: 2026-06-19-bottom-timeline-timescope). Renders a
 * sample entity-lifespan gantt over a plain historical-year domain, with the
 * playhead reflecting the current year. Drag-to-scrub is wired in Task 5.
 */
export function TimelineScope() {
  const { time } = useTimeState();
  const year = instantYear(time);

  return (
    <div className="flex h-full items-stretch">
      <div className="flex w-[150px] flex-none flex-col justify-center px-4 leading-tight">
        <span className="font-mono text-sm tabular-nums">{formatTime(time)}</span>
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {eraFor(year)}
        </span>
      </div>

      <div className="relative min-w-0 flex-1">
        <Timescope
          width="100%"
          height="100%"
          time={year}
          indicator
          sources={{ spans: sampleSpans }}
          series={{
            spans: {
              data: {
                source: 'spans',
                time: { start: 'start', end: 'end' },
                value: { lane: 'lane' },
                range: [0, SAMPLE_LANES],
              },
              track: TRACK,
              chart: {
                marks: [
                  {
                    draw: 'box',
                    using: ['lane@start', 'lane@end'],
                    style: {
                      size: 16,
                      radius: 3,
                      fillColor: ({ data }) => groupColor(data.group),
                      fillOpacity: 0.85,
                      lineWidth: 1.5,
                      lineColor: ({ data }) => groupColor(data.group),
                    },
                  },
                  {
                    draw: 'text',
                    using: 'lane@start',
                    style: {
                      size: 12,
                      text: ({ data }) => data.label,
                      textAlign: 'start',
                      textColor: '#1f2937',
                      textOutline: true,
                      textOutlineColor: '#ffffff',
                      textOutlineWidth: 3,
                      offset: ({ data }) => [(data.end - data.start) * 0.5, 0],
                    },
                  },
                ],
              },
            },
          }}
          tracks={{
            [TRACK]: {
              height: 150,
              timeAxis: {
                timeFormat: (opts) => formatYear(Math.round(opts.time.number())),
              },
            },
          }}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Swap the component into `web/src/app/routes/AtlasLayout.tsx`**

Change the import on line 5:

```tsx
import { TimelineScope } from '@/components/atlas/TimelineScope';
```

Replace the timeline spine block (lines ~40-43) with:

```tsx
      {/* Timeline spine */}
      <div className="h-14 flex-none border-t bg-card">
        <TimelineScope />
      </div>
```

(Height becomes dynamic in Task 6; keep `h-14` for now.)

- [ ] **Step 4: Type-check**

Run: `pnpm --filter @history-mapped/web types:check`
Expected: PASS.
**If the alpha generics reject the inline `sources`/`series`/`tracks` object** (e.g. errors on `using`/`value` key inference), do NOT loosen tsconfig. Instead localize a cast in `TimelineScope.tsx`: import the option types and assert, e.g. `sources={{ spans: sampleSpans } as TimescopeOptionsSources<{ spans: SampleSpan[] }>}` / cast `series` and `tracks` to `TimescopeOptionsSeries<…>`/`TimescopeOptionsTracks<typeof TRACK>` (both exported from `timescope`), or wrap the config with the exported `defineTimescopeSeries`/`defineTimescopeSources`/`defineTimescopeTracks` builders. Re-run until green.

- [ ] **Step 5: Lint**

Run: `pnpm --filter @history-mapped/web lint`
Expected: PASS (0 errors).

- [ ] **Step 6: Visual check (canvas — not unit-testable)**

Run: `pnpm --filter @history-mapped/web dev` and open `http://localhost:5173`.
Expected: a gantt of coloured spans with labels fills the bottom bar; the time axis reads historical years (e.g. `500 BCE`, `1 CE`, `500 CE`); a playhead indicator sits at the current year. Group colours match the map. Stop the dev server when done.

- [ ] **Step 7: Commit**

```bash
git add web/package.json web/pnpm-lock.yaml ../pnpm-lock.yaml web/src/components/atlas/TimelineScope.tsx web/src/app/routes/AtlasLayout.tsx
git commit -m "feat(web): render timescope sample gantt in the bottom bar"
```

---

### Task 5: Wire the playhead (live scrub + commit)

**Files:**
- Modify: `web/src/components/atlas/TimelineScope.tsx`

**Interfaces:**
- Consumes: `useLiveScrub` (`@/hooks`) → `{ liveScrub, setLiveScrub, commit }`; `toYear` (`@/lib/timeline/year`).

- [ ] **Step 1: Add imports**

At the top of `TimelineScope.tsx`, extend the hooks import and add `toYear`:

```tsx
import { useLiveScrub, useTimeState } from '@/hooks';
import { toYear } from '@/lib/timeline/year';
```

- [ ] **Step 2: Derive a display year from live scrub**

Replace the body's first two lines (`const { time } …` / `const year …`) with:

```tsx
  const { time } = useTimeState();
  const { liveScrub, setLiveScrub, commit } = useLiveScrub();
  const committedYear = instantYear(time);
  const displayYear = liveScrub ?? committedYear;
```

- [ ] **Step 3: Use `displayYear` in the readout**

Replace the readout `<span>`s with:

```tsx
        <span className="font-mono text-sm tabular-nums">{formatYear(displayYear)}</span>
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {eraFor(displayYear)}
        </span>
```

(`formatTime` is no longer used here — remove it from the `@/lib/format` import to satisfy `noUnusedLocals`.)

- [ ] **Step 4: Bind the playhead callbacks**

On `<Timescope>`, change `time={year}` to `time={committedYear}` and add, right after `indicator`:

```tsx
          onTimeChanging={(v) => {
            const y = toYear(v);
            if (y !== null) setLiveScrub(y);
          }}
          onTimeChanged={(v) => {
            const y = toYear(v);
            if (y !== null) commit(y);
          }}
```

- [ ] **Step 5: Type-check + lint**

Run: `pnpm --filter @history-mapped/web types:check && pnpm --filter @history-mapped/web lint`
Expected: both PASS.

- [ ] **Step 6: Visual check**

Run: `pnpm --filter @history-mapped/web dev`, open the app.
Expected: dragging the playhead updates the year readout live; on release the URL `?t=` updates and the map re-filters to the new year. Stop the dev server.

- [ ] **Step 7: Commit**

```bash
git add web/src/components/atlas/TimelineScope.tsx
git commit -m "feat(web): wire timescope playhead to time state (live scrub + commit)"
```

---

### Task 6: Collapsible bar (scrubber ↔ gantt)

**Files:**
- Modify: `web/src/components/atlas/TimelineScope.tsx`
- Modify: `web/src/app/routes/AtlasLayout.tsx` (let the slot height follow the component)

**Interfaces:**
- Consumes: `useTimelineExpanded` (`@/hooks`); `cn` (`@/lib/utils`); `ChevronUp`/`ChevronDown` (`lucide-react`).

- [ ] **Step 1: Add imports to `TimelineScope.tsx`**

```tsx
import { ChevronDown, ChevronUp } from 'lucide-react';
import { useLiveScrub, useTimeState, useTimelineExpanded } from '@/hooks';
import { cn } from '@/lib/utils';
```

- [ ] **Step 2: Read expanded state and compute heights**

After the `displayYear` line add:

```tsx
  const { expanded, toggle } = useTimelineExpanded();
  const trackHeight = expanded ? 150 : 28;
```

- [ ] **Step 3: Make the outer container height follow the state**

Change the outermost `<div className="flex h-full items-stretch">` to:

```tsx
    <div className={cn('flex items-stretch transition-[height]', expanded ? 'h-[170px]' : 'h-14')}>
```

- [ ] **Step 4: Add the collapse toggle to the readout column**

Inside the readout column `<div className="flex w-[150px] …">`, add as the last child:

```tsx
        <button
          type="button"
          onClick={toggle}
          aria-label={expanded ? 'Collapse timeline' : 'Expand timeline'}
          className="mt-1 grid size-6 place-items-center self-start rounded-md border bg-card text-muted-foreground hover:bg-muted"
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
        </button>
```

- [ ] **Step 5: Suppress spans + shrink track when collapsed**

Replace the entire `series={{ … }}` prop on `<Timescope>` with the gated version below (collapsed → no marks; the bar becomes a pure axis + playhead scrubber):

```tsx
          series={
            expanded
              ? {
                  spans: {
                    data: {
                      source: 'spans',
                      time: { start: 'start', end: 'end' },
                      value: { lane: 'lane' },
                      range: [0, SAMPLE_LANES],
                    },
                    track: TRACK,
                    chart: {
                      marks: [
                        {
                          draw: 'box',
                          using: ['lane@start', 'lane@end'],
                          style: {
                            size: 16,
                            radius: 3,
                            fillColor: ({ data }) => groupColor(data.group),
                            fillOpacity: 0.85,
                            lineWidth: 1.5,
                            lineColor: ({ data }) => groupColor(data.group),
                          },
                        },
                        {
                          draw: 'text',
                          using: 'lane@start',
                          style: {
                            size: 12,
                            text: ({ data }) => data.label,
                            textAlign: 'start',
                            textColor: '#1f2937',
                            textOutline: true,
                            textOutlineColor: '#ffffff',
                            textOutlineWidth: 3,
                            offset: ({ data }) => [(data.end - data.start) * 0.5, 0],
                          },
                        },
                      ],
                    },
                  },
                }
              : {}
          }
```

Then, in the `tracks` prop, change `height: 150,` to `height: trackHeight,`.

- [ ] **Step 6: Let the layout slot height follow the component**

In `web/src/app/routes/AtlasLayout.tsx`, change the spine wrapper to drop the fixed height:

```tsx
      {/* Timeline spine */}
      <div className="flex-none border-t bg-card">
        <TimelineScope />
      </div>
```

- [ ] **Step 7: Type-check + lint**

Run: `pnpm --filter @history-mapped/web types:check && pnpm --filter @history-mapped/web lint`
Expected: both PASS.

- [ ] **Step 8: Visual check**

Run: `pnpm --filter @history-mapped/web dev`, open the app.
Expected: default is the compact (~56px) scrubber; the chevron expands to the ~170px gantt and back; the playhead drags and commits in both states. Stop the dev server.

- [ ] **Step 9: Commit**

```bash
git add web/src/components/atlas/TimelineScope.tsx web/src/app/routes/AtlasLayout.tsx
git commit -m "feat(web): collapsible bottom timeline (scrubber <-> gantt)"
```

---

### Task 7: Retire the old `Timeline.tsx`

**Files:**
- Delete: `web/src/components/atlas/Timeline.tsx`

- [ ] **Step 1: Confirm parity, then check the blast radius**

If GitNexus MCP tools are available, run `impact({ target: "Timeline", direction: "upstream" })` and confirm the only consumer was `AtlasLayout` (now swapped). Otherwise:

Run: `grep -rn "atlas/Timeline'" web/src` and `grep -rn "\bTimeline\b" web/src/app web/src/components`
Expected: no remaining imports of `@/components/atlas/Timeline` (only `TimelineScope`).

- [ ] **Step 2: Delete the file**

Run: `git rm web/src/components/atlas/Timeline.tsx`

- [ ] **Step 3: Full verification**

Run: `pnpm --filter @history-mapped/web types:check && pnpm --filter @history-mapped/web lint && pnpm --filter @history-mapped/web test && pnpm --filter @history-mapped/web build`
Expected: all PASS (build = `tsc -b && vite build`).

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor(web): remove the superseded static Timeline component"
```

---

## Definition of done

- `TimelineScope` replaces `Timeline` in the bottom slot; old `Timeline.tsx` is gone.
- Collapsible: compact scrubber default; chevron expands to the sample gantt.
- Playhead drag updates the readout live and, on release, the URL `?t=` → the map re-filters.
- Axis labels read as historical BCE/CE years.
- `pnpm --filter @history-mapped/web test | types:check | lint | build` all green.

## Self-review notes (coverage vs spec)

- Deps incl. exact `@kikuchan/decimal@0.1.0-alpha.5` → Task 4 Step 1. Vitest → Task 1.
- Replace `Timeline.tsx`, kept until parity → Task 4 (swap) + Task 7 (delete after parity).
- Sample data at a seam → `sampleSpans.ts` (Task 2). Themed via runtime CSS-var resolution → `colors.ts` (Task 2).
- Fully-wired playhead (live → commit; map reacts via existing effect) → Task 5.
- Collapsible via ephemeral store → Task 3 + Task 6.
- Reuse `format.ts` (`formatYear`/`formatTime`/`eraFor`/`instantYear`); new `year.ts` only converts Decimal→year → Tasks 1, 4, 5.
- BCE/CE axis via `TimeFormatFunc` using `formatYear` → Task 4.
- TDD pure helpers; canvas verified visually → Tasks 1-3 (tests), 4-6 (visual).
- Deferred (NOT in this plan): real span data, range-selection, play/animate, persisted zoom/collapse, backend.
- Alpha-generics risk has a concrete, localized mitigation → Task 4 Step 4.
