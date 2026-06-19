# Mobile-responsive Atlas shell (bottom drawer) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Below `md` (≤767px), replace the desktop sidebar + right panel with a single three-state (peek/half/full) bottom sheet, plus a compact top bar and floating timeline, leaving desktop unchanged.

**Architecture:** `AtlasLayout` render-branches on a new `useIsMobile()` hook into the existing desktop shell or a new `MobileShell`. The mobile shell hosts a `vaul` bottom sheet whose height is the pre-existing `sheet` ephemeral state and whose content (chronicle / detail / list) is a pure function of selection + chronicle state. Detail and chronicle bodies are extracted into chrome-less content components shared by both shells.

**Tech Stack:** React 19, Vite 7, Tailwind v4, TanStack Query, nuqs (URL state), zustand (ephemeral), `vaul` (bottom sheet, NEW), Vitest + Testing Library (test harness, NEW).

**Working directory:** the `develop` worktree at `.claude/worktrees/frontend`. All paths below are relative to that checkout. This is the `web/` host-side Vite app — preview/tests run host-side; no Docker mount dependency.

## Global Constraints

- **Breakpoint:** mobile shell active when `max-width: 767px` (Tailwind `md` boundary). Single source of truth: `useIsMobile()`.
- **Reuse existing state:** the bottom-sheet height is `sheet: 'peek' | 'half' | 'full'` in `web/src/stores/ephemeral.ts` via `useSheet()`. Do NOT add new global sheet state.
- **No desktop behavior change:** desktop renders the identical content as today; refactors are pure moves.
- **Design tokens only:** use existing CSS variables / Tailwind tokens (`card`, `muted`, `border`, group accents). Geist Mono is reserved for data (years, counts). No new colors.
- **vaul version:** add `vaul@^1.1.2` (React 19-compatible). If install resolves a different major, verify its snap-point API before wiring (see Task 5).
- **Commits:** Conventional Commits. Every commit message ends with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- **Run commands from `web/`:** e.g. `cd web && npm test`. NOTE: the concurrent "timescope" agent already installed Vitest and removed the old `Timeline` (now `TimelineScope`). Scripts are `test` (= `vitest run`) and `test:watch` (= `vitest`) — there is NO `test:run`. Run a focused suite with `npm test -- <path-fragment>`.

## Prerequisites (owned by another agent)

Dependency installation is **out of scope for this plan** — a separate agent installs and lockfile-commits the npm packages. This plan only *names* the required deps and *verifies* they resolve before use; it does not run `npm i`. Required additions:

- Dev: `vitest@^3`, `jsdom@^25`, `@testing-library/react@^16`, `@testing-library/dom@^10`, `@testing-library/jest-dom@^6`, `@testing-library/user-event@^14`
- Runtime: `vaul@^1.1.2` (React 19-compatible)

Before starting Task 1, confirm these are present (`ls web/node_modules/vitest web/node_modules/vaul`). If absent, hand back to the dependency agent rather than installing here.

## Testing strategy (read before starting)

`web/` has no test runner today; Task 1 adds one. TDD applies to the **pure, deterministic** units — `useMediaQuery` and the sheet logic in `lib/sheet.ts` (snap mappers, content-kind, selection reducer). Component assembly (vaul sheet, top bar, shells) is **not** unit-tested: vaul needs `ResizeObserver`/pointer APIs jsdom lacks, and the content components depend on TanStack Query + nuqs data hooks whose mocking cost outweighs the value for pure structural code. Those tasks are verified by `npm run types:check`, `npm run lint`, `npm run build`, and a manual Playwright pass at 390×844 and the 767/768px boundary. Each task states its verification explicitly.

---

### Task 1: Vitest + Testing Library harness

**Files:**
- Modify: `web/package.json` (add `test`/`test:run` scripts only — deps owned by the dependency agent)
- Modify: `web/vite.config.ts`
- Create: `web/src/test/setup.ts`
- Create: `web/src/test/sanity.test.ts`

**Interfaces:**
- Produces: `npm run test` (watch) and `npm run test:run` (CI) scripts; a jsdom test environment with `@testing-library/jest-dom` matchers and a default `window.matchMedia` stub.

- [ ] **Step 1: Verify dev dependencies are present**

The dependency agent installs these (see Prerequisites). Confirm they resolve:
```bash
ls web/node_modules/vitest web/node_modules/jsdom web/node_modules/@testing-library/react web/node_modules/@testing-library/jest-dom
```
Expected: all four paths exist. If any is missing, stop and hand back to the dependency agent — do NOT run `npm i` here.

- [ ] **Step 2: Add test scripts to `web/package.json`**

In the `"scripts"` block add:
```json
    "test": "vitest",
    "test:run": "vitest run"
```

- [ ] **Step 3: Wire Vitest into `web/vite.config.ts`**

Change the import and add a `test` block:
```ts
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: false,
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    hmr: { host: 'localhost', port: 5173 },
    watch: { usePolling: true },
  },
});
```

- [ ] **Step 4: Create `web/src/test/setup.ts`**

```ts
import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => cleanup());

// jsdom has no matchMedia; provide a no-op default. Individual tests that
// exercise useMediaQuery override window.matchMedia themselves.
if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}
```

- [ ] **Step 5: Create a sanity test `web/src/test/sanity.test.ts`**

```ts
import { describe, expect, it } from 'vitest';

describe('test harness', () => {
  it('runs', () => {
    expect(1 + 1).toBe(2);
  });
});
```

- [ ] **Step 6: Run the suite**

Run: `cd web && npm run test:run`
Expected: PASS — 1 passed (sanity.test.ts).

- [ ] **Step 7: Commit**

```bash
git add web/package.json web/vite.config.ts web/src/test
git commit -m "test(web): add vitest + testing-library harness"
```
(Commit only the `scripts` change in `package.json`, the config, and the test files. The dependency entries + lockfile are owned by the dependency agent.)

---

### Task 2: `useMediaQuery` / `useIsMobile`

**Files:**
- Create: `web/src/hooks/useMediaQuery.ts`
- Create: `web/src/hooks/useMediaQuery.test.ts`
- Modify: `web/src/hooks/index.ts`

**Interfaces:**
- Produces: `useMediaQuery(query: string): boolean` and `useIsMobile(): boolean` (= `useMediaQuery('(max-width: 767px)')`), both exported from `@/hooks`.

- [ ] **Step 1: Write the failing test `web/src/hooks/useMediaQuery.test.ts`**

```ts
import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useIsMobile, useMediaQuery } from './useMediaQuery';

type Listener = (e: { matches: boolean }) => void;

/** Install a controllable matchMedia; returns a setter that flips matches. */
function mockMatchMedia(initial: boolean) {
  let matches = initial;
  const listeners = new Set<Listener>();
  window.matchMedia = vi.fn().mockImplementation((media: string) => ({
    get matches() {
      return matches;
    },
    media,
    addEventListener: (_: string, cb: Listener) => listeners.add(cb),
    removeEventListener: (_: string, cb: Listener) => listeners.delete(cb),
    addListener: (cb: Listener) => listeners.add(cb),
    removeListener: (cb: Listener) => listeners.delete(cb),
    dispatchEvent: () => true,
  }));
  return (next: boolean) => {
    matches = next;
    listeners.forEach((cb) => cb({ matches: next }));
  };
}

afterEach(() => vi.restoreAllMocks());

describe('useMediaQuery', () => {
  it('returns the initial match state', () => {
    mockMatchMedia(true);
    const { result } = renderHook(() => useMediaQuery('(max-width: 767px)'));
    expect(result.current).toBe(true);
  });

  it('updates when the query match changes', () => {
    const set = mockMatchMedia(false);
    const { result } = renderHook(() => useMediaQuery('(max-width: 767px)'));
    expect(result.current).toBe(false);
    act(() => set(true));
    expect(result.current).toBe(true);
  });

  it('useIsMobile is false above the breakpoint', () => {
    mockMatchMedia(false);
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm run test:run -- useMediaQuery`
Expected: FAIL — cannot resolve `./useMediaQuery`.

- [ ] **Step 3: Implement `web/src/hooks/useMediaQuery.ts`**

```ts
import { useCallback, useSyncExternalStore } from 'react';

/** Reactive `matchMedia` boolean. SSR-safe (server snapshot = false). */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const mql = window.matchMedia(query);
      mql.addEventListener('change', onChange);
      return () => mql.removeEventListener('change', onChange);
    },
    [query],
  );
  const getSnapshot = () => window.matchMedia(query).matches;
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}

/** True on phones / small portrait tablets (Tailwind `md` boundary). */
export function useIsMobile(): boolean {
  return useMediaQuery('(max-width: 767px)');
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm run test:run -- useMediaQuery`
Expected: PASS — 3 passed.

- [ ] **Step 5: Export from the barrel `web/src/hooks/index.ts`**

Under the `// URL-state` / hooks section add:
```ts
export { useMediaQuery, useIsMobile } from './useMediaQuery';
```

- [ ] **Step 6: Commit**

```bash
git add web/src/hooks/useMediaQuery.ts web/src/hooks/useMediaQuery.test.ts web/src/hooks/index.ts
git commit -m "feat(web): add useMediaQuery/useIsMobile hook"
```

---

### Task 3: Pure sheet logic + selector/sync hooks

**Files:**
- Create: `web/src/lib/sheet.ts`
- Create: `web/src/lib/sheet.test.ts`
- Create: `web/src/hooks/useSheetContent.ts`
- Create: `web/src/hooks/useSheetSelectionSync.ts`
- Modify: `web/src/hooks/index.ts`

**Interfaces:**
- Consumes: `SheetHeight` from `@/stores/ephemeral`; `useSheet`, `useSelection`, `useChronicleNav` from `@/hooks`.
- Produces:
  - `SNAP_POINTS: readonly ['130px', 0.55, 0.97]`
  - `heightToSnap(h: SheetHeight): number | string`
  - `snapToHeight(snap: number | string | null): SheetHeight`
  - `type SheetContentKind = 'chronicle' | 'detail' | 'list'`
  - `sheetContentKind(a: { chronicleActive: boolean; hasSelection: boolean }): SheetContentKind`
  - `nextSheetForSelection(a: { prevSel: string | null; nextSel: string | null; current: SheetHeight }): SheetHeight`
  - `useSheetContent(): SheetContentKind`
  - `useSheetSelectionSync(): void`

- [ ] **Step 1: Write the failing test `web/src/lib/sheet.test.ts`**

```ts
import { describe, expect, it } from 'vitest';
import {
  heightToSnap,
  nextSheetForSelection,
  sheetContentKind,
  SNAP_POINTS,
  snapToHeight,
} from './sheet';

describe('snap mappers', () => {
  it('maps heights to snap points round-trip', () => {
    expect(heightToSnap('peek')).toBe(SNAP_POINTS[0]);
    expect(heightToSnap('half')).toBe(SNAP_POINTS[1]);
    expect(heightToSnap('full')).toBe(SNAP_POINTS[2]);
    expect(snapToHeight(SNAP_POINTS[0])).toBe('peek');
    expect(snapToHeight(SNAP_POINTS[1])).toBe('half');
    expect(snapToHeight(SNAP_POINTS[2])).toBe('full');
  });
  it('falls back to peek for unknown/null snap', () => {
    expect(snapToHeight(null)).toBe('peek');
    expect(snapToHeight(0.42)).toBe('peek');
  });
});

describe('sheetContentKind', () => {
  it('chronicle wins over selection', () => {
    expect(sheetContentKind({ chronicleActive: true, hasSelection: true })).toBe('chronicle');
  });
  it('selection shows detail', () => {
    expect(sheetContentKind({ chronicleActive: false, hasSelection: true })).toBe('detail');
  });
  it('otherwise list', () => {
    expect(sheetContentKind({ chronicleActive: false, hasSelection: false })).toBe('list');
  });
});

describe('nextSheetForSelection', () => {
  it('raises peek to half when an entity is selected', () => {
    expect(nextSheetForSelection({ prevSel: null, nextSel: 'e:x', current: 'peek' })).toBe('half');
  });
  it('keeps a non-peek height on selection', () => {
    expect(nextSheetForSelection({ prevSel: null, nextSel: 'e:x', current: 'full' })).toBe('full');
  });
  it('drops full to half on deselection', () => {
    expect(nextSheetForSelection({ prevSel: 'e:x', nextSel: null, current: 'full' })).toBe('half');
  });
  it('leaves half alone on deselection', () => {
    expect(nextSheetForSelection({ prevSel: 'e:x', nextSel: null, current: 'half' })).toBe('half');
  });
  it('no change when selection is unchanged', () => {
    expect(nextSheetForSelection({ prevSel: 'e:x', nextSel: 'e:x', current: 'peek' })).toBe('peek');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- lib/sheet`
Expected: FAIL — cannot resolve `./sheet`.

- [ ] **Step 3: Implement `web/src/lib/sheet.ts`**

```ts
import type { SheetHeight } from '@/stores/ephemeral';

/** vaul snap points, low → high. Index-aligned to ORDER below. */
export const SNAP_POINTS = ['130px', 0.55, 0.97] as const;
const ORDER: readonly SheetHeight[] = ['peek', 'half', 'full'];

export function heightToSnap(h: SheetHeight): number | string {
  return SNAP_POINTS[ORDER.indexOf(h)];
}

export function snapToHeight(snap: number | string | null): SheetHeight {
  const i = SNAP_POINTS.findIndex((s) => s === snap);
  return i === -1 ? 'peek' : ORDER[i];
}

export type SheetContentKind = 'chronicle' | 'detail' | 'list';

/** What the sheet shows. Chronicle tour wins, then a selected entity, else the list. */
export function sheetContentKind(a: {
  chronicleActive: boolean;
  hasSelection: boolean;
}): SheetContentKind {
  if (a.chronicleActive) return 'chronicle';
  if (a.hasSelection) return 'detail';
  return 'list';
}

/** Height policy when selection changes: keep the map partly visible. */
export function nextSheetForSelection(a: {
  prevSel: string | null;
  nextSel: string | null;
  current: SheetHeight;
}): SheetHeight {
  if (!a.prevSel && a.nextSel) return a.current === 'peek' ? 'half' : a.current;
  if (a.prevSel && !a.nextSel) return a.current === 'full' ? 'half' : a.current;
  return a.current;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test -- lib/sheet`
Expected: PASS — all sheet tests green.

- [ ] **Step 5: Implement `web/src/hooks/useSheetContent.ts`**

```ts
import { useChronicleNav, useSelection } from '@/hooks';
import { type SheetContentKind, sheetContentKind } from '@/lib/sheet';

/** Reactive sheet content kind from selection + chronicle URL state. */
export function useSheetContent(): SheetContentKind {
  const { isActive } = useChronicleNav();
  const { sel } = useSelection();
  return sheetContentKind({ chronicleActive: isActive, hasSelection: sel != null });
}
```

- [ ] **Step 6: Implement `web/src/hooks/useSheetSelectionSync.ts`**

```ts
import { useEffect, useRef } from 'react';
import { useSelection, useSheet } from '@/hooks';
import { nextSheetForSelection } from '@/lib/sheet';

/** Mobile only: nudge the sheet height when the selection changes. */
export function useSheetSelectionSync(): void {
  const { sel } = useSelection();
  const { sheet, setSheet } = useSheet();
  const prev = useRef<string | null>(sel);

  useEffect(() => {
    const next = nextSheetForSelection({ prevSel: prev.current, nextSel: sel, current: sheet });
    if (next !== sheet) setSheet(next);
    prev.current = sel;
  }, [sel, sheet, setSheet]);
}
```

- [ ] **Step 7: Export hooks from `web/src/hooks/index.ts`**

Add:
```ts
export { useSheetContent } from './useSheetContent';
export { useSheetSelectionSync } from './useSheetSelectionSync';
```

- [ ] **Step 8: Verify types + lint, then commit**

Run: `cd web && npm test -- lib/sheet && npm run types:check && npm run lint`
Expected: tests PASS, no type errors, no lint errors.
```bash
git add web/src/lib/sheet.ts web/src/lib/sheet.test.ts web/src/hooks/useSheetContent.ts web/src/hooks/useSheetSelectionSync.ts web/src/hooks/index.ts
git commit -m "feat(web): sheet snap/content logic + selector hooks"
```

---

### Task 4: Extract chrome-less content components

Pure structural moves: the inner JSX of `DetailPanel` and `ChroniclePlayer` becomes exported content components; the existing components become thin wrappers rendering them. No JSX/logic changes — desktop output is byte-identical.

**Files:**
- Modify: `web/src/components/atlas/DetailPanel.tsx`
- Modify: `web/src/components/atlas/ChroniclePlayer.tsx`

**Interfaces:**
- Produces: `export function DetailPanelContent(): JSX.Element | null` (everything currently inside `DetailPanel`'s `<aside>` *except* the top "Detail"/close bar). `export function ChroniclePlayerContent()` (everything inside `ChroniclePlayer`'s `<aside>` *except* the top "Exit tour"/Chronicle bar).
- Consumed by: Task 5 (`SheetContent`).

- [ ] **Step 1: Refactor `DetailPanel.tsx`**

Keep all helpers (`StatCell`, `yearText`, `relStart`, `temporalText`, `otherSide`, `RelationshipTimeline`) unchanged. Move the body so the file ends with:

```tsx
/** Chrome-less detail body — shared by the desktop aside and the mobile sheet.
 *  Reads the selection itself; renders nothing when nothing is selected. */
export function DetailPanelContent() {
  const { sel } = useSelection();
  const { enter } = useChronicleNav();
  const { data: entity, isLoading, isError } = useEntity(sel);
  const { data: connections } = useEntityConnections(sel);
  const { data: chronicles } = useEntityChronicles(sel);

  const relChronicle = useMemo(() => {
    const m = new Map<string, { title: string; slug: string }>();
    chronicles?.data.forEach((c) =>
      c.relationship_ids.forEach((rid) => {
        if (!m.has(rid)) m.set(rid, { title: c.title, slug: c.slug });
      }),
    );
    return m;
  }, [chronicles]);

  if (!sel) return null;

  return (
    <>
      {isLoading && <p className="px-4 py-3 text-sm text-muted-foreground">Loading…</p>}
      {isError && <p className="px-4 py-3 text-sm text-destructive">Could not load entity.</p>}
      {entity && (
        <>
          {/* …MOVE the existing entity JSX block here VERBATIM:
               title block, stats grid, summary, relationships, footer… */}
        </>
      )}
    </>
  );
}

/** Desktop right aside: chrome + the shared content. */
export function DetailPanel() {
  const { sel, clear } = useSelection();
  if (!sel) return null;
  return (
    <aside className="flex h-full w-[380px] max-w-[90vw] flex-none flex-col overflow-y-auto border-l bg-card">
      <div className="flex items-center justify-between px-3 py-2.5">
        <span className="px-1.5 text-xs font-medium text-muted-foreground">Detail</span>
        <button
          type="button"
          onClick={clear}
          className="grid size-7 place-items-center rounded-md text-muted-foreground hover:bg-muted"
          aria-label="Close detail"
        >
          <X size={16} />
        </button>
      </div>
      <DetailPanelContent />
    </aside>
  );
}
```

Concretely: cut the current `{isLoading && …}`, `{isError && …}`, and `{entity && ( … )}` JSX out of `DetailPanel` and paste it (unchanged) into `DetailPanelContent`'s return where the comment marks. The `<aside>` wrapper now contains only the close bar + `<DetailPanelContent />`. The previous `overflow-y-auto` on the aside stays.

- [ ] **Step 2: Refactor `ChroniclePlayer.tsx`**

Keep `StepEntities` and `WhatChanged` unchanged. Restructure the export the same way:

```tsx
/** Chrome-less chronicle body — shared by the desktop aside and the mobile sheet. */
export function ChroniclePlayerContent() {
  const { chron, step, next, prev, goto } = useChronicleNav();
  const { data, isLoading, isError } = useChronicle(chron);
  const { setInstant } = useTimeState();

  const entries = data?.entries ?? [];
  const total = entries.length;
  const current = entries[step];

  useEffect(() => {
    if (current?.start_year != null) setInstant(current.start_year);
  }, [current?.entry_id, current?.start_year, setInstant]);

  return (
    <div className="flex h-full flex-col">
      {isLoading && <p className="p-4 text-sm text-muted-foreground">Loading…</p>}
      {isError && <p className="p-4 text-sm text-destructive">Could not load chronicle.</p>}
      {data && (
        <>
          {/* …MOVE the existing title/progress, scrollable narrative, and
               prev/next footer JSX here VERBATIM (everything that was inside
               `{data && (…)}`)… */}
        </>
      )}
    </div>
  );
}

/** Desktop left aside while a chronicle is active: chrome + shared content. */
export function ChroniclePlayer() {
  const { exit } = useChronicleNav();
  return (
    <aside className="flex h-full w-[380px] max-w-[90vw] flex-none flex-col border-l bg-card">
      <div className="flex items-center justify-between border-b px-3 py-2">
        <button
          type="button"
          onClick={exit}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[13px] text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <ChevronLeft size={15} /> Exit tour
        </button>
        <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground">
          <Route size={12} /> Chronicle
        </span>
      </div>
      <ChroniclePlayerContent />
    </aside>
  );
}
```

Note: `exit` is read only in the wrapper now; `next/prev/goto/step/chron` stay in the content. Keep the `Route`/`ChevronLeft` imports (still used).

- [ ] **Step 3: Verify nothing broke**

Run: `cd web && npm run types:check && npm run lint && npm run build`
Expected: clean type check, no lint errors, successful build.

- [ ] **Step 4: Manual desktop sanity**

Run `cd web && npm run dev`, open at desktop width, select an entity (detail aside renders as before), open a chronicle (player renders as before). Confirm no visual change.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/atlas/DetailPanel.tsx web/src/components/atlas/ChroniclePlayer.tsx
git commit -m "refactor(web): extract DetailPanelContent/ChroniclePlayerContent"
```

---

### Task 5: vaul bottom sheet (`MobileSheet` + `SheetContent`)

**Files:**
- Create: `web/src/components/atlas/SheetContent.tsx`
- Create: `web/src/components/atlas/MobileSheet.tsx`
- (`web/package.json` `vaul` entry is added by the dependency agent — not committed here)

**Interfaces:**
- Consumes: `useSheet` (`@/hooks`); `SNAP_POINTS`, `heightToSnap`, `snapToHeight` (`@/lib/sheet`); `useSheetContent`; `DetailPanelContent`, `ChroniclePlayerContent`; `BrowseTab`, `ChronicleList`; `useSelection`.
- Produces: `export function MobileSheet(): JSX.Element` — a persistent, non-modal vaul drawer bound to `sheet` state.

- [ ] **Step 1: Verify vaul is present**

The dependency agent installs `vaul` (see Prerequisites). Confirm: `ls web/node_modules/vaul`. If missing, hand back — do NOT run `npm i` here. Then confirm the installed snap-point API matches the props used below (`snapPoints`, `activeSnapPoint`, `setActiveSnapPoint`, `modal`, `dismissible`). If unsure, check current docs via context7 (`resolve-library-id vaul` → `query-docs`) before Step 3.

- [ ] **Step 2: Create `web/src/components/atlas/SheetContent.tsx`**

```tsx
import { ChevronLeft } from 'lucide-react';
import { useState } from 'react';
import {
  ChroniclePlayerContent,
} from '@/components/atlas/ChroniclePlayer';
import { DetailPanelContent } from '@/components/atlas/DetailPanel';
import { BrowseTab } from '@/components/atlas/BrowseTab';
import { ChronicleList } from '@/components/atlas/ChronicleList';
import { useSelection, useSheetContent } from '@/hooks';
import { cn } from '@/lib/utils';

type Tab = 'entities' | 'chronicles';

/** Detail in the sheet: a back-to-results bar over the shared detail body. */
function SheetDetail() {
  const { clear } = useSelection();
  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-none items-center px-2 py-1.5">
        <button
          type="button"
          onClick={clear}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[13px] text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <ChevronLeft size={15} /> Results
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <DetailPanelContent />
      </div>
    </div>
  );
}

/** List in the sheet: two tabs over the existing browse / chronicle lists. */
function SheetList() {
  const [tab, setTab] = useState<Tab>('entities');
  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-none gap-0.5 rounded-lg bg-muted p-0.5">
        {(['entities', 'chronicles'] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={cn(
              'flex-1 rounded-md py-1.5 text-xs font-medium capitalize transition-colors',
              tab === t ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground',
            )}
          >
            {t}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        {tab === 'entities' ? <BrowseTab /> : <ChronicleList />}
      </div>
    </div>
  );
}

/** Sheet body: chronicle tour, entity detail, or the list. */
export function SheetContent() {
  const kind = useSheetContent();
  if (kind === 'chronicle') return <ChroniclePlayerContent />;
  if (kind === 'detail') return <SheetDetail />;
  return <SheetList />;
}
```

- [ ] **Step 3: Create `web/src/components/atlas/MobileSheet.tsx`**

```tsx
import { Drawer } from 'vaul';
import { SheetContent } from '@/components/atlas/SheetContent';
import { useSheet } from '@/hooks';
import { heightToSnap, SNAP_POINTS, snapToHeight } from '@/lib/sheet';

/**
 * Persistent, non-modal bottom sheet (peek/half/full). Replaces the desktop
 * sidebar + right panel below `md`. Height is the shared `sheet` ephemeral
 * state; vaul's active snap point is bound two-way to it.
 */
export function MobileSheet() {
  const { sheet, setSheet } = useSheet();
  return (
    <Drawer.Root
      open
      modal={false}
      dismissible={false}
      snapPoints={[...SNAP_POINTS]}
      activeSnapPoint={heightToSnap(sheet)}
      setActiveSnapPoint={(snap) =>
        setSheet(snapToHeight(snap as number | string | null))
      }
    >
      <Drawer.Portal>
        <Drawer.Content
          aria-describedby={undefined}
          className="fixed inset-x-0 bottom-0 z-20 flex h-full max-h-[97%] flex-col rounded-t-2xl border bg-card p-3 outline-none"
        >
          <div
            aria-hidden
            className="mx-auto mb-2 h-1.5 w-10 flex-none rounded-full bg-border"
          />
          <Drawer.Title className="sr-only">Atlas browser</Drawer.Title>
          <div className="min-h-0 flex-1">
            <SheetContent />
          </div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
```

- [ ] **Step 4: Verify build/types**

Run: `cd web && npm run types:check && npm run build`
Expected: clean. (If vaul prop names differ in the installed version, adjust per its docs — keep the two-way `sheet`↔snap binding.)

- [ ] **Step 5: Commit**

```bash
git add web/src/components/atlas/SheetContent.tsx web/src/components/atlas/MobileSheet.tsx
git commit -m "feat(web): vaul bottom sheet with content switching"
```
(The `vaul` dependency entry + lockfile are committed by the dependency agent.)

---

### Task 6: `MobileTopBar`

**Files:**
- Create: `web/src/components/atlas/MobileTopBar.tsx`

**Interfaces:**
- Consumes: `useCommandPalette`, `useView` (`@/hooks`).
- Produces: `export function MobileTopBar(): JSX.Element`.

- [ ] **Step 1: Create `web/src/components/atlas/MobileTopBar.tsx`**

```tsx
import { Compass, Globe, Layers, MapPin, Search, SlidersHorizontal } from 'lucide-react';
import { useState } from 'react';
import { useCommandPalette, useView } from '@/hooks';
import { cn } from '@/lib/utils';

/** Mobile header: brand mark · search pill (opens ⌘K palette) · tools menu. */
export function MobileTopBar() {
  const { setOpen } = useCommandPalette();
  const { view, setView } = useView();
  const [tools, setTools] = useState(false);

  return (
    <header className="relative flex h-[52px] flex-none items-center gap-2 border-b bg-card px-3">
      <span className="grid size-8 flex-none place-items-center rounded-lg bg-primary text-primary-foreground">
        <Compass size={16} />
      </span>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-9 flex-1 items-center gap-2 rounded-lg border bg-muted/50 px-3 text-[13px] text-muted-foreground"
      >
        <Search size={15} />
        <span className="flex-1 text-left">Search the atlas…</span>
      </button>
      <button
        type="button"
        onClick={() => setTools((v) => !v)}
        aria-label="Tools"
        aria-expanded={tools}
        className="grid size-9 flex-none place-items-center rounded-lg border bg-card text-muted-foreground"
      >
        <SlidersHorizontal size={16} />
      </button>

      {tools && (
        <div className="absolute right-3 top-[54px] z-30 w-44 rounded-xl border bg-popover p-1.5 shadow-lg">
          <div className="flex gap-0.5 rounded-lg bg-muted p-0.5">
            {([['map', 'Map', MapPin], ['globe', 'Globe', Globe]] as const).map(
              ([v, label, Icon]) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => {
                    setView(v);
                    setTools(false);
                  }}
                  className={cn(
                    'inline-flex flex-1 items-center justify-center gap-1.5 rounded-md py-1.5 text-xs font-medium',
                    view === v ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground',
                  )}
                >
                  <Icon size={14} /> {label}
                </button>
              ),
            )}
          </div>
          <button
            type="button"
            className="mt-1 flex w-full items-center gap-2 rounded-md px-2 py-2 text-[13px] text-muted-foreground hover:bg-muted"
          >
            <Layers size={15} /> Layers
          </button>
        </div>
      )}
    </header>
  );
}
```

- [ ] **Step 2: Verify + commit**

Run: `cd web && npm run types:check && npm run lint`
Expected: clean.
```bash
git add web/src/components/atlas/MobileTopBar.tsx
git commit -m "feat(web): mobile top bar (search pill + tools menu)"
```

---

### Task 7: Compact timeline variant

**Files:**
- Modify: `web/src/components/atlas/Timeline.tsx`

**Interfaces:**
- Produces: `Timeline` accepts an optional `{ compact?: boolean }` prop. `compact` hides the zoom buttons and the wide year/era column label width; default `false` ⇒ desktop unchanged.

- [ ] **Step 1: Add the `compact` prop to `Timeline.tsx`**

Change the signature and gate the zoom controls:
```tsx
export function Timeline({ compact = false }: { compact?: boolean } = {}) {
  const { time } = useTimeState();
  const year = instantYear(time);
  const pct = Math.max(0, Math.min(100, ((year - AXIS_MIN) / (AXIS_MAX - AXIS_MIN)) * 100));

  return (
    <div className={compact ? 'flex h-12 items-center gap-2.5 px-3' : 'flex h-14 items-center gap-3 px-4'}>
      {/* play button — unchanged */}
      {/* year/era column: */}
      <div className={cn('flex flex-none flex-col leading-tight', compact ? 'w-[96px]' : 'w-[150px]')}>
        {/* …existing year + era spans unchanged… */}
      </div>
      {/* track — unchanged */}
      {!compact && (
        <div className="flex flex-none items-center gap-1">
          {/* …existing zoom-out / zoom-in buttons unchanged… */}
        </div>
      )}
    </div>
  );
}
```
Add `import { cn } from '@/lib/utils';` at the top. Keep the play button and the `<div className="relative h-8 flex-1">` track block exactly as-is.

- [ ] **Step 2: Verify desktop unaffected + commit**

Run: `cd web && npm run types:check && npm run lint && npm run build`
Expected: clean; desktop Timeline (no prop) renders identically.
```bash
git add web/src/components/atlas/Timeline.tsx
git commit -m "feat(web): add compact variant to Timeline"
```

---

### Task 8: `MobileShell` composition

**Files:**
- Create: `web/src/components/atlas/MobileShell.tsx`

**Interfaces:**
- Consumes: `MobileTopBar`, `MobileSheet`, `Timeline` (compact), `MapCanvas`, `CommandPalette`, `useSheetSelectionSync`.
- Produces: `export function MobileShell(): JSX.Element`.

- [ ] **Step 1: Create `web/src/components/atlas/MobileShell.tsx`**

```tsx
import { CommandPalette } from '@/components/atlas/CommandPalette';
import { MobileSheet } from '@/components/atlas/MobileSheet';
import { MobileTopBar } from '@/components/atlas/MobileTopBar';
import { Timeline } from '@/components/atlas/Timeline';
import { MapCanvas } from '@/components/map/MapCanvas';
import { useSheetSelectionSync } from '@/hooks';

/** Touch shell (≤ md): compact top bar, full-bleed map with a floating
 *  timeline, and a persistent bottom sheet that replaces both desktop asides. */
export function MobileShell() {
  useSheetSelectionSync();
  return (
    <div className="flex h-dvh w-screen flex-col overflow-hidden bg-background text-foreground">
      <MobileTopBar />
      <div className="relative min-h-0 flex-1 overflow-hidden">
        <MapCanvas />
        <div className="pointer-events-none absolute inset-x-0 top-0 z-10 p-2">
          <div className="pointer-events-auto rounded-xl border bg-card/95 shadow-sm backdrop-blur">
            <Timeline compact />
          </div>
        </div>
      </div>
      <MobileSheet />
      <CommandPalette />
    </div>
  );
}
```

- [ ] **Step 2: Verify + commit**

Run: `cd web && npm run types:check && npm run lint && npm run build`
Expected: clean.
```bash
git add web/src/components/atlas/MobileShell.tsx
git commit -m "feat(web): compose MobileShell"
```

---

### Task 9: Render-branch `AtlasLayout`

**Files:**
- Create: `web/src/components/atlas/DesktopShell.tsx`
- Modify: `web/src/app/routes/AtlasLayout.tsx`

**Interfaces:**
- Consumes: `useIsMobile`, `MobileShell`.
- Produces: `DesktopShell` (today's layout, verbatim) and an `AtlasLayout` that branches on `useIsMobile()`.

- [ ] **Step 1: Create `web/src/components/atlas/DesktopShell.tsx`**

Move the current body of `AtlasLayout` here verbatim (including the `RightPanel` helper):
```tsx
import { ChroniclePlayer } from '@/components/atlas/ChroniclePlayer';
import { CommandPalette } from '@/components/atlas/CommandPalette';
import { DetailPanel } from '@/components/atlas/DetailPanel';
import { LeftSidebar } from '@/components/atlas/LeftSidebar';
import { Timeline } from '@/components/atlas/Timeline';
import { TopBar } from '@/components/atlas/TopBar';
import { MapCanvas } from '@/components/map/MapCanvas';
import { useChronicleNav } from '@/hooks';

/** The right panel hosts the chronicle tour OR the entity detail — never both. */
function RightPanel() {
  const { isActive } = useChronicleNav();
  return isActive ? <ChroniclePlayer /> : <DetailPanel />;
}

export function DesktopShell() {
  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground">
      <TopBar />
      <div className="relative min-h-0 flex-1 overflow-hidden">
        <MapCanvas />
        <div className="absolute inset-y-0 left-0 z-10">
          <LeftSidebar />
        </div>
        <div className="absolute inset-y-0 right-0 z-10">
          <RightPanel />
        </div>
      </div>
      <div className="h-14 flex-none border-t bg-card">
        <Timeline />
      </div>
      <CommandPalette />
    </div>
  );
}
```

- [ ] **Step 2: Replace `web/src/app/routes/AtlasLayout.tsx`**

```tsx
import { DesktopShell } from '@/components/atlas/DesktopShell';
import { MobileShell } from '@/components/atlas/MobileShell';
import { useIsMobile } from '@/hooks';

/**
 * Top-level shell selector. Below `md` the touch shell (bottom sheet) renders;
 * above it, the desktop sidebar layout. Only one mounts at a time, so the heavy
 * sidebar and the vaul sheet never coexist. Crossing the breakpoint live
 * remounts MapCanvas, which restores its view from the URL `bbox`.
 */
export function AtlasLayout() {
  const isMobile = useIsMobile();
  return isMobile ? <MobileShell /> : <DesktopShell />;
}
```

- [ ] **Step 3: Verify build + both layouts**

Run: `cd web && npm run types:check && npm run lint && npm run build`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/atlas/DesktopShell.tsx web/src/app/routes/AtlasLayout.tsx
git commit -m "feat(web): render-branch AtlasLayout into desktop/mobile shells"
```

---

### Task 10: End-to-end verification & docs

**Files:**
- Modify: `docs/plans/STATUS.md` (if the plan is tracked there)

- [ ] **Step 1: Full check**

Run: `cd web && npm run test:run && npm run types:check && npm run lint && npm run build`
Expected: all green.

- [ ] **Step 2: Manual mobile pass (Playwright or devtools device mode)**

Serve `cd web && npm run dev`. At 390×844 verify:
- Bottom sheet visible at **peek**; drag handle raises to **half** (list) and **full**.
- Tap a list row → content switches to **detail**; "‹ Results" returns to list and the sheet drops from full to half.
- Tap a map pin → sheet rises to at least half showing detail.
- Open a chronicle → sheet shows the chronicle player; "Exit tour" / back returns to list.
- Search pill opens the command palette.
- Tools menu toggles Map/Globe.
At the **767/768px** boundary: ≤767 shows the mobile shell, ≥768 shows the desktop sidebar layout; both render without console errors.

- [ ] **Step 3: Update plan status (if applicable) and commit**

If `docs/plans/STATUS.md` tracks this work, add/flip its row to reflect shipped. Then:
```bash
git add -A
git commit -m "docs: mark mobile-responsive drawer shipped"
```

- [ ] **Step 4: Finish the branch**

Use the superpowers:finishing-a-development-branch skill to choose merge / PR / cleanup for `develop`.

---

## Self-Review

**Spec coverage:**
- Render-branch (spec §Architecture) → Task 9. `useIsMobile` md breakpoint → Task 2.
- One sheet, peek/half/full via `sheet` state → Tasks 3, 5.
- vaul mechanism → Task 5. Content switching (chronicle/detail/list) → Tasks 3, 5.
- Content/chrome refactor (DetailPanel, ChroniclePlayer) → Task 4. BrowseTab/ChronicleList reused directly → Task 5.
- Selection→height behavior (§State & behavior) → Task 3 (`nextSheetForSelection`) + Task 8 (`useSheetSelectionSync`). Note: implemented as "selection raises peek→half; deselection drops full→half" — a deterministic, origin-independent refinement of the spec's list-tap→full wording, keeping map context and avoiding forking the shared `BrowseTab`. Flagged for stakeholder confirmation at first review.
- Compact top bar + floating timeline (§Mobile shell) → Tasks 6, 7, 8.
- Vitest tests (§Testing) → Tasks 1–3 (pure units); component/integration via build + manual (§Testing strategy).
- vaul dependency floor → Task 5 / Global Constraints.

**Placeholder scan:** The two refactor steps in Task 4 say "MOVE the existing JSX VERBATIM" rather than re-pasting ~120 unchanged lines — this is a deliberate, exact move instruction (the source already exists in-repo and is unchanged), not a TODO. All new files carry complete code.

**Type consistency:** `SheetHeight` (`'peek'|'half'|'full'`) and `SheetContentKind` (`'chronicle'|'detail'|'list'`) are used consistently across `lib/sheet.ts`, the hooks, and the components. `heightToSnap`/`snapToHeight` names match between Task 3 (definition) and Task 5 (use). `DetailPanelContent`/`ChroniclePlayerContent` names match between Task 4 (definition) and Task 5 (use).
