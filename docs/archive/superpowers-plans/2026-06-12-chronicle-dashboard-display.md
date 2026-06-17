# Chronicle Display on the Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface chronicles on the map dashboard — a searchable list, an entry drill-down, and entry-driven jumps that set the dashboard year and entity selection so a chronicle reads as a guided tour over the existing year-driven map.

**Architecture:** A two-tab right aside (Chronicles | Selection). `ChroniclePanel` lists summaries from `GET /v1/chronicles`; selecting one loads `GET /v1/chronicles/{slug}` into `ChronicleDetail`; selecting an entry calls `applyEntry`, which reuses the dashboard's existing `selectedYear` + `selectedEntityId` state. No parallel map state.

**Tech Stack:** React 19, TanStack Query v5, Inertia, TypeScript, Vitest (admin frontend under `api/resources/js`).

**Spec:** [../specs/2026-06-12-chronicle-dashboard-display-design.md](../superpowers-specs/2026-06-12-chronicle-dashboard-display-design.md)

**Dependencies:** Works on today's API. Enhanced by sub-project D (explicit entry/chronicle temporal fields + index year filter) — adopt when available; do not block.

---

## File structure

| File | Change |
|------|--------|
| `api/resources/js/types/chronicle.ts` | Create: `ChronicleSummary`, `Chronicle`, `ChronicleEntry` types |
| `api/resources/js/hooks/use-chronicles.ts` | Create: `useChronicles`, `useChronicle` query hooks |
| `api/resources/js/components/chronicle-panel.tsx` | Create: searchable summary list |
| `api/resources/js/components/chronicle-detail.tsx` | Create: entries + stepper + helpers |
| `api/resources/js/pages/dashboard.tsx` | Modify: aside tabs, chronicle state, `applyEntry` |
| `api/resources/js/components/historical-map-viewer.tsx` | (optional) `flyTo` prop |
| Tests | `api/resources/js/components/__tests__/*`, `pages/__tests__/dashboard.test.tsx` |

> Run JS tests: `pnpm --filter <admin-workspace> test <path>` (or the repo's configured Vitest command).

---

## Task 1: Chronicle TS types

**Files:** Create `api/resources/js/types/chronicle.ts`; Test `api/resources/js/types/__tests__/chronicle.types.test.ts` (optional type-only)

- [ ] **Step 1: Write the types** to match the API resources:

```ts
export interface ChronicleSummary {
  chronicle_id: string;
  title: string;
  slug: string;
  source_type: string | null;
  status: string | null;
  entry_count: number;
  created_at: string;
  updated_at: string;
}
export interface ChronicleEntry {
  entry_id: string;
  sequence_order: number;
  narrative_text: string;
  notes: string | null;
  timestamp: number | null;          // derived year from ChronicleEntryResource
  start_year?: number | null;        // present once sub-project D serializes it
  primary_relationship_id: string | null;
  primary_relationship?: { source_entity_id: string; target_entity_id: string } | null;
  secondary_entities?: Array<{ entity_id: string; name: string }>;
  approximate_location?: { lng: number; lat: number } | null;
}
export interface Chronicle extends ChronicleSummary {
  entries: ChronicleEntry[];
}
```

- [ ] **Step 2: Commit** `feat(web): chronicle dashboard types`

## Task 2: Query hooks

**Files:** Create `api/resources/js/hooks/use-chronicles.ts`; Test `api/resources/js/hooks/__tests__/use-chronicles.test.ts`

- [ ] **Step 1: Write the failing test** — `useChronicles({search:'x'})` calls `GET /api/v1/chronicles?search=x` and returns the `data` array; `useChronicle('slug')` calls `GET /api/v1/chronicles/slug` and is disabled when slug is null. Mock `fetch`.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — two `useQuery` hooks keyed `['chronicles', params]` and `['chronicle', slug]` (the latter `enabled: !!slug`), parsing the `{data}` envelope; pass `signal` into `fetch`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(web): useChronicles/useChronicle query hooks`

## Task 3: ChroniclePanel (list + search)

**Files:** Create `api/resources/js/components/chronicle-panel.tsx`; Test `api/resources/js/components/__tests__/chronicle-panel.test.tsx`

- [ ] **Step 1: Write the failing tests** — renders summary rows (title + source_type badge + entry_count); typing in the search box debounces and re-requests with `search`; clicking a row calls `onSelect(slug)`; empty result shows an empty state.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — `ChroniclePanel({ onSelect })` using `useChronicles`; debounced search input; scrollable list; a "load more"/pager for the 20-per-page index.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(web): ChroniclePanel list + search`

## Task 4: ChronicleDetail (entries + stepper + helpers)

**Files:** Create `api/resources/js/components/chronicle-detail.tsx`; Test `api/resources/js/components/__tests__/chronicle-detail.test.tsx`

- [ ] **Step 1: Write the failing tests** — given a chronicle, entries render in `sequence_order`; selecting an entry calls `onSelectEntry(entry)`; prev/next move the active entry; the `entryYear`/`entryPrimaryEntityId` helpers return the derived values.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** —

```ts
export const entryYear = (e: ChronicleEntry): number | null =>
  e.start_year ?? e.timestamp ?? null;
export const entryPrimaryEntityId = (e: ChronicleEntry): string | null =>
  e.primary_relationship?.source_entity_id ?? e.secondary_entities?.[0]?.entity_id ?? null;
```

`ChronicleDetail({ slug, onSelectEntry, onBack })` uses `useChronicle(slug)`, renders ordered entries (narrative snippet, `entryYear`, entity chips), a prev/next stepper tracking `activeEntryId`, and a back affordance.

- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(web): ChronicleDetail entries + stepper`

## Task 5: Wire into the dashboard aside (tabs + applyEntry)

**Files:** Modify `api/resources/js/pages/dashboard.tsx`; Test `api/resources/js/pages/__tests__/dashboard.test.tsx`

- [ ] **Step 1: Write the failing tests** — selecting an entry sets `selectedYear` to `entryYear(entry)` and `selectedEntityId` to `entryPrimaryEntityId(entry)`; a same-year entry does **not** trigger a new map fetch (query cache hit); the aside switches to the Selection tab when an entity becomes selected, with a control back to Chronicles.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — add `selectedChronicleSlug`/`activeEntryId` state; render the aside as tabs `[Chronicles | Selection]` (Chronicles = `ChroniclePanel` → `ChronicleDetail`; Selection = existing panel); implement

```ts
const applyEntry = (entry: ChronicleEntry) => {
  const y = entryYear(entry);
  if (y !== null) setSelectedYear(clampYear(String(y)));
  const id = entryPrimaryEntityId(entry);
  if (id) setSelectedEntityId(id);
};
```

Guard `setSelectedYear` so an unchanged year doesn't churn the map. Default tab Chronicles; auto-switch to Selection on entity select.

- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(web): chronicles tab on the dashboard with entry-driven map jumps`

## Task 6 (optional): Map fly-to on entry select

**Files:** Modify `api/resources/js/components/historical-map-viewer.tsx`, `dashboard.tsx`; Test `historical-map-viewer.test.tsx`

- [ ] **Step 1: Write the failing test** — passing a new `flyTo={lng,lat}` calls `map.flyTo` once per change.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — add an optional `flyTo` prop; in an effect keyed on it, call `map.flyTo({center:[lng,lat]})` when `mapReady`. In `applyEntry`, pass `entry.approximate_location` when present.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `feat(web): pan the map to a chronicle entry's location`

---

## Self-review (coverage)

- Types → T1. Hooks → T2. List/search → T3. Entries/stepper/helpers → T4. Dashboard tabs + `applyEntry` → T5. Fly-to → T6 (optional). Spec §5–§8 covered. The sub-project-D enhancements (explicit `start_year`, index year-filter, `approximate_location`) are consumed opportunistically by `entryYear`/T6 and noted as a follow-up — no task blocks on D.

## Execution handoff

Subagent-driven recommended. T1–T2 (types + hooks) first; T6 is optional polish. If the 22rem aside feels cramped in review, switching Chronicles to a collapsible left rail is a localized change to T5.
