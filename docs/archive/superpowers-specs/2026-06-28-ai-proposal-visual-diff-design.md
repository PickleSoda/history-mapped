# AI Proposal Visual Diff — Design

**Date:** 2026-06-28
**Status:** Approved — ready for implementation plan
**Surface:** Inertia admin (`api/resources/js`) — AI chat proposal card

## Problem

When the admin AI agent proposes a change, the chat renders a **Proposed changes**
card (`api/resources/js/components/ai/proposal-card.tsx`). Each part shows only a
one-line human summary (`human_diff.summary`) plus Apply / Discard buttons. The
operator approving the change cannot see the actual before → after values — e.g.
"Update fields on Georgian SSR: founding_year" tells them *which* field changes
but not *from what, to what*.

The richer field-level data **already exists** and is **already sent to the
frontend**; the card simply discards it.

## Key finding: the data is already there

Every tool's `buildParts()` stores a full `human_diff` array, and it is returned
verbatim in both code paths:

- **Live proposals** — `AgentTool::handle()` returns
  `$change->parts()->get(['key', 'tool', 'human_diff'])` (the whole `human_diff`).
- **Resumed sessions** — `AiSessionController` (`api/app/Http/Controllers/Admin/Ai/AiSessionController.php:90`)
  returns `'human_diff' => $p->human_diff` (the model casts the JSON column to an array).

The only reason the card shows just a summary is the **frontend**: the TypeScript
type narrows `human_diff` to `{ summary: string }` (in `proposal-card.tsx:17` and
`reconstruct-session-messages.ts:17`) and the render reads only `.summary`.

**Therefore this feature is frontend-only: no backend change, no migration, no API change.**

### The heterogeneous `human_diff` shapes

Confirmed shapes produced by the tools (all carry `summary`; the extra keys vary):

| Tool | Extra keys | Example |
|------|-----------|---------|
| `UpdateEntityFields` | `diff: { field: { from, to } }` | `{ summary, diff: { founding_year: { from: 1921, to: 1922 } } }` |
| `SetEntityWikidata` | `from`, `to`, `verified_label` | `{ summary, from: null, to: "Q130229", verified_label: "Georgian SSR" }` |
| `SetEntityLocation` | `from: [lon,lat]\|null`, `to: [lon,lat]` | `{ summary, from: null, to: [44.78, 41.71] }` |
| `CreateEntity` | `fields: {...}` | `{ summary, fields: { name: "...", entity_type: "..." } }` |
| `CreateChronicle` | `fields: {...}` | `{ summary, fields: { title: "..." } }` |
| `UpdateChronicleEntry` | `fields: {...}` | `{ summary, fields: { entry_id, ... } }` |
| `MergeDuplicateEntities` | `survivor_id/name`, `loser_id/name` | `{ summary, survivor_name, loser_name }` |
| `CreateRelationship` | (none) | `{ summary }` |

## Goal

Replace the single summary line in each proposal part with an **expandable,
normalized before → after diff**. Summary stays visible by default; an operator
can expand to see per-field old → new values. Works identically for live and
resumed proposals.

## Architecture

A pure frontend normalizer plus an expandable diff component.

```
human_diff (already full, live + resumed)
   → parseProposal / reconstruct-session-messages   (widen TS types, thread `tool`)
   → normalizeHumanDiff(tool, human_diff): DiffRow[] (pure, defensive, total)
   → <ProposalDiff>                                  (toggle + red/green rows)
```

No network change. The normalizer is **total** — any unknown or malformed shape
returns `[]`, and a part with no rows renders **no toggle** (graceful fallback to
the current summary-only line). A newly-added backend tool therefore cannot break
the card.

## Components

### 1. `api/resources/js/lib/human-diff.ts` (new)

The normalizer + value formatter. No React.

```ts
export type DiffRow = {
    label: string;            // field name / human label, e.g. "founding_year"
    from: string | null;      // formatted old value, or null when there is none (creates)
    to: string | null;        // formatted new value, or null
    kind: 'change' | 'create' | 'merge';
};

export function normalizeHumanDiff(tool: string, humanDiff: unknown): DiffRow[];
```

Mapping rules (driven by the **shape** of `human_diff`, with `tool` as a hint; shape
checks make it resilient to tools sharing a shape):

- Has `diff` object (`{ field: { from, to } }`) → one `kind:'change'` row per field:
  `{ label: field, from: format(from), to: format(to), kind: 'change' }`.
- Has top-level `from`/`to` (Wikidata, location) → one `kind:'change'` row.
  - Label: a readable noun derived from the tool (`set_entity_wikidata` → `"Wikidata QID"`,
    `set_entity_location` → `"Location"`), falling back to a title-cased tool name.
  - Wikidata: append `verified_label` to the `to` value when present → `"Q130229 (Georgian SSR)"`.
- Has `fields` object (creates) → one `kind:'create'` row per field:
  `{ label: field, from: null, to: format(value), kind: 'create' }`.
- Has `survivor_name`/`loser_name` (merge) → one `kind:'merge'` row:
  `{ label: 'merge', from: loser_name, to: survivor_name, kind: 'merge' }`.
- Otherwise (summary-only, or unrecognized) → `[]`.

Private `formatValue(v: unknown): string`:
- `null` / `undefined` → `"—"`
- `number` / `boolean` → `String(v)`
- `string` → the string, truncated to ~120 chars with `…` if longer
- array → elements `formatValue`-d and joined with `", "` (coords render `44.78, 41.71`)
- object → compact `JSON.stringify`, truncated to ~120 chars
- never throws

### 2. `api/resources/js/components/ai/proposal-diff.tsx` (new)

```tsx
export function ProposalDiff({ tool, humanDiff }: { tool: string; humanDiff: unknown }): JSX.Element | null;
```

- Calls `normalizeHumanDiff(tool, humanDiff)`. If `rows.length === 0` → returns `null`
  (no toggle, card shows just the summary).
- Otherwise renders a real `<button>` toggle (`aria-expanded`, local `useState`):
  collapsed shows `▾ Show changes`, expanded shows `▸ Hide changes` and the rows.
- Default state: **collapsed**.
- Row rendering by `kind`:
  - `change` → red line `− {from}` then green line `+ {to}` under a `label` caption.
  - `create` → single green line `+ {to}` under `label`.
  - `merge` → `{from} → {to}` under `label`.
- Styling consistent with the amber card: `text-red-600`/`text-green-600`
  (+ dark variants), `font-mono` for values, small text. Values use
  `break-words`/`whitespace-pre-wrap` so long strings wrap inside the card.

### 3. `api/resources/js/components/ai/proposal-card.tsx` (modified)

- Widen `ProposalPart`:
  ```ts
  export type ProposalPart = {
      key: string;
      tool: string;                                          // already sent by backend
      human_diff: { summary: string } & Record<string, unknown>;
      status?: 'pending' | 'applied' | 'discarded';
      result_id?: string | null;
  };
  ```
- Under each part's summary line, render
  `<ProposalDiff tool={part.tool} humanDiff={part.human_diff} />`.
- Render the diff for all parts regardless of status (applied/discarded parts keep
  their existing locked badge; the diff stays collapsed by default). No change to the
  apply/discard/loading/error flow.

### 4. `api/resources/js/lib/reconstruct-session-messages.ts` (modified)

- Widen its `human_diff` type the same way and ensure `tool` is carried through to the
  reconstructed `ProposalPart` (the session controller already returns `tool`), so
  resumed proposals render diffs identically to live ones.

## Error handling

- `normalizeHumanDiff` and `formatValue` are total — they never throw; malformed,
  partial, or unknown shapes degrade to `[]` (summary-only, no toggle).
- The existing card behavior (Apply / Discard / loading / error / locked replayed
  parts) is untouched.

## Testing (vitest, TDD)

**`api/resources/js/lib/__tests__/human-diff.test.ts` (new):**
- `UpdateEntityFields` `diff` → one `change` row per field, correct from/to.
- `CreateEntity` `fields` → `create` rows, `from === null`.
- `SetEntityWikidata` `from/to` + `verified_label` → `to` includes the label.
- `SetEntityLocation` array coords → formatted `"lon, lat"` string.
- `MergeDuplicateEntities` → one `merge` row loser → survivor.
- summary-only (`CreateRelationship`) → `[]`.
- malformed / unknown shape → `[]` (no throw).
- `formatValue` edges: `null` → `"—"`, array, long string truncation.

**`api/resources/js/components/__tests__/proposal-card.test.tsx` (extended):**
- A part with diff data renders a `Show changes` toggle; clicking reveals rows with old/new values; clicking again hides them.
- A summary-only part renders **no** toggle.
- Applied / discarded parts still render their locked badge (regression).

## Out of scope (YAGNI)

- Word-/character-level intra-string diffing (only whole old value vs whole new value).
- Visual map diffing of geometry/coordinates.
- Any backend, API, migration, or `human_diff` shape change.

## Global constraints

- Frontend-only; backend untouched.
- Gates run in the `app` container: `npx vitest run`, `npm run types:check`,
  `npm run lint:check` (0 errors; the 2 pre-existing `dashboard.tsx` warnings are
  acceptable), `npm run build`.
- No Wayfinder regeneration (no route changes).
- Work on `develop` (branch off it, merge back to it).
