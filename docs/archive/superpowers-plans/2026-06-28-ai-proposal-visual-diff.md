# AI Proposal Visual Diff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single summary line in each AI proposal part with an expandable, normalized before→after diff.

**Architecture:** Pure frontend. The backend already stores and returns the full `human_diff` for both live (`AgentTool::handle`) and resumed (`AiSessionController`) proposals — only the TypeScript types narrow it to `{ summary: string }` and the card renders `.summary`. Add (1) a pure normalizer that flattens any `human_diff` shape into a uniform `DiffRow[]`, (2) an expandable `<ProposalDiff>` component, and (3) wiring into `ProposalCard` plus widened types. No backend, migration, or API change.

**Tech Stack:** React 19, TypeScript, Tailwind v4, Vitest + @testing-library/react. Admin frontend at `api/resources/js`.

**Spec:** `docs/superpowers/specs/2026-06-28-ai-proposal-visual-diff-design.md`

## Global Constraints

- **Frontend-only.** No backend, API, migration, or `human_diff` shape change.
- **Run all JS gates on the HOST via `pnpm --filter`, NOT `npx` in the container.**
  `npx prettier` inside the `app` container auto-downloads a bare `prettier@3.9.5`
  without the Tailwind plugin and gives false passes; the host `pnpm --filter` uses
  the lockfile-pinned `prettier@3.8.1` + `prettier-plugin-tailwindcss@0.6.14` that CI
  uses. This is a pure frontend feature, so the host toolchain is authoritative and
  avoids the Docker stale-mount issue entirely.
- Gate commands (cwd is resolved by `--filter`; test paths are relative to `api/`):
  - Test one file: `pnpm --filter @history-mapped/api exec vitest run <path>`
  - All admin tests: `pnpm --filter @history-mapped/api exec vitest run`
  - Types: `pnpm --filter @history-mapped/api run types:check` (expect 0 errors)
  - Lint: `pnpm --filter @history-mapped/api run lint:check` (expect 0 errors; the 2
    pre-existing `dashboard.tsx` warnings are acceptable)
  - Format check: `pnpm --filter @history-mapped/api run format:check`
  - Auto-format: `pnpm --filter @history-mapped/api run format`
  - Build: `pnpm --filter @history-mapped/api run build`
- **ESLint rules to respect** (they fail the build otherwise): `import/order`,
  `@stylistic/padding-line-between-statements` (blank line before `return`, between
  declarations and statements), `curly` (every `if` needs braces — no single-line
  `if (x) return;`).
- **Run `format` before every commit** so `format:check` stays green.
- Work on `develop` (branch off it, merge back to it).

---

### Task 1: `human-diff` normalizer

Pure module that turns any `human_diff` object into `DiffRow[]`. No React. This is the
whole domain logic; the UI in later tasks is a thin renderer over it.

**Files:**
- Create: `api/resources/js/lib/human-diff.ts`
- Test: `api/resources/js/lib/__tests__/human-diff.test.ts`

**Interfaces:**
- Produces:
  - `type DiffRow = { label: string; from: string | null; to: string | null; kind: 'change' | 'create' | 'merge' }`
  - `function normalizeHumanDiff(tool: string, humanDiff: unknown): DiffRow[]`
  - `function formatValue(v: unknown): string`

- [ ] **Step 1: Write the failing test**

Create `api/resources/js/lib/__tests__/human-diff.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { formatValue, normalizeHumanDiff } from '@/lib/human-diff';

describe('formatValue', () => {
    it('renders null/undefined as an em dash', () => {
        expect(formatValue(null)).toBe('—');
        expect(formatValue(undefined)).toBe('—');
    });

    it('joins array values (e.g. coordinates)', () => {
        expect(formatValue([44.78, 41.71])).toBe('44.78, 41.71');
    });

    it('truncates long strings', () => {
        const long = 'x'.repeat(200);
        const out = formatValue(long);

        expect(out.length).toBeLessThan(200);
        expect(out.endsWith('…')).toBe(true);
    });
});

describe('normalizeHumanDiff', () => {
    it('maps a field-level edit diff to change rows', () => {
        const rows = normalizeHumanDiff('update_entity_fields', {
            summary: 'Update fields',
            diff: {
                founding_year: { from: 1921, to: 1922 },
                summary: { from: 'Old', to: 'New' },
            },
        });

        expect(rows).toEqual([
            { label: 'founding_year', from: '1921', to: '1922', kind: 'change' },
            { label: 'summary', from: 'Old', to: 'New', kind: 'change' },
        ]);
    });

    it('maps a create fields object to create rows with null from', () => {
        const rows = normalizeHumanDiff('create_entity', {
            summary: 'Create entity',
            fields: { name: 'Kingdom of Georgia', entity_type: 'political_entity' },
        });

        expect(rows).toEqual([
            { label: 'name', from: null, to: 'Kingdom of Georgia', kind: 'create' },
            { label: 'entity_type', from: null, to: 'political_entity', kind: 'create' },
        ]);
    });

    it('appends the verified label to a Wikidata to-value', () => {
        const rows = normalizeHumanDiff('set_entity_wikidata', {
            summary: 'Set QID',
            from: null,
            to: 'Q130229',
            verified_label: 'Georgian SSR',
        });

        expect(rows).toEqual([
            {
                label: 'Wikidata QID',
                from: '—',
                to: 'Q130229 (Georgian SSR)',
                kind: 'change',
            },
        ]);
    });

    it('formats location coordinates in a from/to row', () => {
        const rows = normalizeHumanDiff('set_entity_location', {
            summary: 'Move entity',
            from: null,
            to: [44.78, 41.71],
        });

        expect(rows).toEqual([
            { label: 'Location', from: '—', to: '44.78, 41.71', kind: 'change' },
        ]);
    });

    it('maps a merge to a single merge row (loser → survivor)', () => {
        const rows = normalizeHumanDiff('merge_duplicate_entities', {
            summary: 'Merge',
            survivor_name: 'Georgian SSR',
            loser_name: 'Gruzia',
        });

        expect(rows).toEqual([
            { label: 'merge', from: 'Gruzia', to: 'Georgian SSR', kind: 'merge' },
        ]);
    });

    it('returns [] for a summary-only diff', () => {
        expect(
            normalizeHumanDiff('create_relationship', { summary: 'Link A → B' }),
        ).toEqual([]);
    });

    it('returns [] for malformed input without throwing', () => {
        expect(normalizeHumanDiff('x', null)).toEqual([]);
        expect(normalizeHumanDiff('x', 'a string')).toEqual([]);
        expect(normalizeHumanDiff('x', 42)).toEqual([]);
        expect(normalizeHumanDiff('x', { summary: 's', fields: {} })).toEqual([]);
    });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm --filter @history-mapped/api exec vitest run resources/js/lib/__tests__/human-diff.test.ts`
Expected: FAIL — `Failed to resolve import "@/lib/human-diff"` / module not found.

- [ ] **Step 3: Write the implementation**

Create `api/resources/js/lib/human-diff.ts`:

```ts
export type DiffRow = {
    label: string;
    from: string | null;
    to: string | null;
    kind: 'change' | 'create' | 'merge';
};

const MAX_LEN = 120;

function truncate(s: string): string {
    return s.length > MAX_LEN ? `${s.slice(0, MAX_LEN)}…` : s;
}

function isRecord(v: unknown): v is Record<string, unknown> {
    return typeof v === 'object' && v !== null && !Array.isArray(v);
}

/** Format any value into a short display string. Total — never throws. */
export function formatValue(v: unknown): string {
    if (v === null || v === undefined) {
        return '—';
    }

    if (typeof v === 'number' || typeof v === 'boolean') {
        return String(v);
    }

    if (typeof v === 'string') {
        return truncate(v);
    }

    if (Array.isArray(v)) {
        return truncate(v.map(formatValue).join(', '));
    }

    try {
        return truncate(JSON.stringify(v));
    } catch {
        return '—';
    }
}

function labelForTool(tool: string): string {
    if (tool === 'set_entity_wikidata') {
        return 'Wikidata QID';
    }

    if (tool === 'set_entity_location') {
        return 'Location';
    }

    if (!tool) {
        return 'Change';
    }

    const spaced = tool.replace(/_/g, ' ');

    return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/**
 * Flatten a stored `human_diff` (heterogeneous per tool) into uniform diff rows.
 * Total and defensive: unknown or malformed shapes return [] so the card falls
 * back to its summary line and a new backend tool can never break rendering.
 */
export function normalizeHumanDiff(tool: string, humanDiff: unknown): DiffRow[] {
    if (!isRecord(humanDiff)) {
        return [];
    }

    // 1) Field-level edits: { diff: { field: { from, to } } }
    const diff = humanDiff.diff;

    if (isRecord(diff)) {
        const rows: DiffRow[] = [];

        for (const [field, change] of Object.entries(diff)) {
            if (isRecord(change) && ('from' in change || 'to' in change)) {
                rows.push({
                    label: field,
                    from: formatValue(change.from),
                    to: formatValue(change.to),
                    kind: 'change',
                });
            }
        }

        if (rows.length > 0) {
            return rows;
        }
    }

    // 2) Create field-lists: { fields: {...} }
    const fields = humanDiff.fields;

    if (isRecord(fields)) {
        return Object.entries(fields).map(([field, value]) => ({
            label: field,
            from: null,
            to: formatValue(value),
            kind: 'create' as const,
        }));
    }

    // 3) Merge: { survivor_name, loser_name }
    if ('survivor_name' in humanDiff || 'loser_name' in humanDiff) {
        return [
            {
                label: 'merge',
                from: formatValue(humanDiff.loser_name),
                to: formatValue(humanDiff.survivor_name),
                kind: 'merge',
            },
        ];
    }

    // 4) Top-level from/to: Wikidata, location
    if ('from' in humanDiff || 'to' in humanDiff) {
        let to = formatValue(humanDiff.to);

        if (typeof humanDiff.verified_label === 'string' && humanDiff.to != null) {
            to = `${to} (${humanDiff.verified_label})`;
        }

        return [
            {
                label: labelForTool(tool),
                from: formatValue(humanDiff.from),
                to,
                kind: 'change',
            },
        ];
    }

    // 5) Summary-only / unrecognized
    return [];
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm --filter @history-mapped/api exec vitest run resources/js/lib/__tests__/human-diff.test.ts`
Expected: PASS — all cases green.

- [ ] **Step 5: Format, lint, and commit**

```bash
pnpm --filter @history-mapped/api run format
pnpm --filter @history-mapped/api run lint:check
git add api/resources/js/lib/human-diff.ts api/resources/js/lib/__tests__/human-diff.test.ts
git commit -m "feat(ai): normalizeHumanDiff — flatten proposal human_diff to diff rows"
```

Expected: lint 0 errors; commit succeeds.

---

### Task 2: `ProposalDiff` expandable component

A thin renderer over `normalizeHumanDiff`. Shows a toggle only when there are rows;
collapsed by default; reveals red/green rows on expand.

**Files:**
- Create: `api/resources/js/components/ai/proposal-diff.tsx`
- Test: `api/resources/js/components/ai/__tests__/proposal-diff.test.tsx`

**Interfaces:**
- Consumes: `normalizeHumanDiff`, `DiffRow` from `@/lib/human-diff` (Task 1).
- Produces: `function ProposalDiff({ tool, humanDiff }: { tool?: string; humanDiff: unknown })` — returns the diff element or `null`. **Do not annotate the return type** (the codebase leaves component return types inferred; an explicit `JSX.Element` can fail `types:check` under the React 19 JSX transform).

- [ ] **Step 1: Write the failing test**

Create `api/resources/js/components/ai/__tests__/proposal-diff.test.tsx`:

```tsx
// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it } from 'vitest';
import { ProposalDiff } from '@/components/ai/proposal-diff';

afterEach(() => {
    cleanup();
});

describe('ProposalDiff', () => {
    it('renders nothing when the diff is summary-only', () => {
        const { container } = render(
            <ProposalDiff tool="create_relationship" humanDiff={{ summary: 's' }} />,
        );

        expect(container).toBeEmptyDOMElement();
    });

    it('shows a toggle and reveals/hides rows on click', () => {
        render(
            <ProposalDiff
                tool="update_entity_fields"
                humanDiff={{
                    summary: 'Update fields',
                    diff: { founding_year: { from: 1921, to: 1922 } },
                }}
            />,
        );

        // Collapsed by default: values hidden, toggle present.
        const toggle = screen.getByRole('button', { name: /show changes/i });

        expect(toggle).toHaveAttribute('aria-expanded', 'false');
        expect(screen.queryByText(/1922/)).not.toBeInTheDocument();

        // Expand → rows visible.
        fireEvent.click(toggle);
        expect(
            screen.getByRole('button', { name: /hide changes/i }),
        ).toHaveAttribute('aria-expanded', 'true');
        expect(screen.getByText(/1921/)).toBeInTheDocument();
        expect(screen.getByText(/1922/)).toBeInTheDocument();

        // Collapse again → rows hidden.
        fireEvent.click(screen.getByRole('button', { name: /hide changes/i }));
        expect(screen.queryByText(/1922/)).not.toBeInTheDocument();
    });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm --filter @history-mapped/api exec vitest run resources/js/components/ai/__tests__/proposal-diff.test.tsx`
Expected: FAIL — cannot resolve `@/components/ai/proposal-diff`.

- [ ] **Step 3: Write the implementation**

Create `api/resources/js/components/ai/proposal-diff.tsx`:

```tsx
import { useState } from 'react';
import { normalizeHumanDiff } from '@/lib/human-diff';

/**
 * Expandable before→after diff for a single proposal part. Renders nothing when
 * the part's human_diff has no structured rows (summary-only tools), so the card
 * gracefully shows just its summary line.
 */
export function ProposalDiff({
    tool,
    humanDiff,
}: {
    tool?: string;
    humanDiff: unknown;
}) {
    const [open, setOpen] = useState(false);
    const rows = normalizeHumanDiff(tool ?? '', humanDiff);

    if (rows.length === 0) {
        return null;
    }

    return (
        <div className="mt-1">
            <button
                type="button"
                aria-expanded={open}
                onClick={() => setOpen((o) => !o)}
                className="text-xs text-amber-700 hover:underline dark:text-amber-300"
            >
                {open ? '▾ Hide changes' : '▸ Show changes'}
            </button>
            {open && (
                <dl className="mt-1 space-y-1">
                    {rows.map((row, idx) => (
                        <div key={idx} className="text-xs">
                            <dt className="text-muted-foreground">{row.label}</dt>
                            <dd className="font-mono break-words whitespace-pre-wrap">
                                {row.kind === 'create' ? (
                                    <span className="text-green-600 dark:text-green-400">
                                        + {row.to}
                                    </span>
                                ) : row.kind === 'merge' ? (
                                    <span>
                                        {row.from} → {row.to}
                                    </span>
                                ) : (
                                    <>
                                        <span className="block text-red-600 line-through dark:text-red-400">
                                            − {row.from}
                                        </span>
                                        <span className="block text-green-600 dark:text-green-400">
                                            + {row.to}
                                        </span>
                                    </>
                                )}
                            </dd>
                        </div>
                    ))}
                </dl>
            )}
        </div>
    );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm --filter @history-mapped/api exec vitest run resources/js/components/ai/__tests__/proposal-diff.test.tsx`
Expected: PASS.

- [ ] **Step 5: Format, lint, and commit**

```bash
pnpm --filter @history-mapped/api run format
pnpm --filter @history-mapped/api run lint:check
git add api/resources/js/components/ai/proposal-diff.tsx api/resources/js/components/ai/__tests__/proposal-diff.test.tsx
git commit -m "feat(ai): ProposalDiff — expandable before/after diff component"
```

Expected: lint 0 errors; commit succeeds.

---

### Task 3: Wire `ProposalDiff` into `ProposalCard` + widen types

Render the diff under each part's summary line, widen the `human_diff`/`tool` types
so the structured data type-checks, and widen the session-payload type so resumed
proposals type-check identically. Add integration/regression tests.

**Files:**
- Modify: `api/resources/js/components/ai/proposal-card.tsx` (types at lines 15–20; part render loop at lines 189–244)
- Modify: `api/resources/js/lib/reconstruct-session-messages.ts` (type at lines 12–21)
- Test: `api/resources/js/components/__tests__/proposal-card.test.tsx` (extend)

**Interfaces:**
- Consumes: `ProposalDiff` from `@/components/ai/proposal-diff` (Task 2).
- Produces: widened `ProposalPart` type (adds `tool?: string`, widens `human_diff`).

- [ ] **Step 1: Write the failing tests**

Append these tests inside the `describe('ProposalCard', …)` block in
`api/resources/js/components/__tests__/proposal-card.test.tsx` (before its closing
`});`). They rely on the real `normalizeHumanDiff`, so use real diff data:

```tsx
    it('renders an expandable diff for a part with structured human_diff', () => {
        const withDiff: Proposal = {
            proposal_id: 'prop-diff',
            parts: [
                {
                    key: 'fields',
                    tool: 'update_entity_fields',
                    human_diff: {
                        summary: 'Update fields on Georgian SSR',
                        diff: { founding_year: { from: 1921, to: 1922 } },
                    },
                },
            ],
        };
        render(<ProposalCard proposal={withDiff} />);

        // Summary still shown; diff collapsed until toggled.
        expect(
            screen.getByText('Update fields on Georgian SSR'),
        ).toBeInTheDocument();
        expect(screen.queryByText(/1922/)).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: /show changes/i }));
        expect(screen.getByText(/1922/)).toBeInTheDocument();
    });

    it('shows no diff toggle for a summary-only part', () => {
        const summaryOnly: Proposal = {
            proposal_id: 'prop-summary',
            parts: [
                {
                    key: 'rel',
                    tool: 'create_relationship',
                    human_diff: { summary: 'Link founder → person' },
                },
            ],
        };
        render(<ProposalCard proposal={summaryOnly} />);

        expect(
            screen.queryByRole('button', { name: /show changes/i }),
        ).not.toBeInTheDocument();
    });
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pnpm --filter @history-mapped/api exec vitest run resources/js/components/__tests__/proposal-card.test.tsx`
Expected: FAIL — the "expandable diff" test fails (no `Show changes` button yet; the card ignores the diff data).

- [ ] **Step 3: Widen the `ProposalPart` type and render `ProposalDiff`**

In `api/resources/js/components/ai/proposal-card.tsx`:

Add the import in the internal (`@/`) group. `import/order` sorts that group
alphabetically, so `@/components/ai/proposal-diff` goes **before**
`@/components/ui/button` (i.e. right after the `import { useRef, useState } from 'react';`
line and before the existing `@/components/ui/*` imports):

```tsx
import { ProposalDiff } from '@/components/ai/proposal-diff';
```

If `lint:check` reports an `import/order` error, run
`pnpm --filter @history-mapped/api run lint` (autofix) to reorder, then re-run
`lint:check`.

Replace the `ProposalPart` type (currently lines 15–20):

```tsx
export type ProposalPart = {
    key: string;
    tool?: string;
    human_diff: { summary: string } & Record<string, unknown>;
    status?: 'pending' | 'applied' | 'discarded';
    result_id?: string | null;
};
```

Replace the part render block (currently the `proposal.parts.map((part) => { … })`
body at lines 189–244) so the existing flex row is wrapped and the diff renders
below it. The existing status/button logic is unchanged — only the surrounding
element structure changes:

```tsx
                {proposal.parts.map((part) => {
                    const status = partStatus[part.key];

                    return (
                        <div key={part.key}>
                            <div className="flex items-center justify-between gap-2">
                                <span className="min-w-0 flex-1 text-sm text-foreground">
                                    {part.human_diff.summary}
                                </span>
                                {status === 'loading' ? (
                                    <span className="text-xs text-muted-foreground">
                                        Saving…
                                    </span>
                                ) : status === 'applied' ? (
                                    <span className="flex items-center gap-1 text-xs text-green-600">
                                        <CheckCircle className="size-3.5" />
                                        Applied
                                    </span>
                                ) : status === 'discarded' ? (
                                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                                        <XCircle className="size-3.5" />
                                        Discarded
                                    </span>
                                ) : status === 'error' ? (
                                    <span className="text-xs text-red-600">
                                        Error — try again
                                    </span>
                                ) : (
                                    <span className="flex shrink-0 gap-1">
                                        <Button
                                            size="sm"
                                            variant="default"
                                            className="h-7 px-2 text-xs"
                                            onClick={() =>
                                                void act(part.key, 'apply')
                                            }
                                        >
                                            Apply
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            className="h-7 px-2 text-xs"
                                            onClick={() =>
                                                void act(part.key, 'discard')
                                            }
                                        >
                                            Discard
                                        </Button>
                                    </span>
                                )}
                            </div>
                            <ProposalDiff
                                tool={part.tool}
                                humanDiff={part.human_diff}
                            />
                        </div>
                    );
                })}
```

- [ ] **Step 4: Widen the session-payload type**

In `api/resources/js/lib/reconstruct-session-messages.ts`, widen the `human_diff`
field of `SessionProposal.parts` (currently line 17) so resumed proposals carry the
structured data in the type as well as at runtime:

```ts
        human_diff: { summary: string } & Record<string, unknown>;
```

- [ ] **Step 5: Run the full admin test suite**

Run: `pnpm --filter @history-mapped/api exec vitest run`
Expected: PASS — new diff tests green; all pre-existing tests (including
`proposal-card` apply/discard/locked-replay and `reconstruct-session-messages`) still
green.

- [ ] **Step 6: Types, lint, format, build**

```bash
pnpm --filter @history-mapped/api run types:check
pnpm --filter @history-mapped/api run lint:check
pnpm --filter @history-mapped/api run format
pnpm --filter @history-mapped/api run format:check
pnpm --filter @history-mapped/api run build
```

Expected: types 0 errors; lint 0 errors (2 pre-existing `dashboard.tsx` warnings ok);
format:check clean; build succeeds.

- [ ] **Step 7: Commit**

```bash
git add api/resources/js/components/ai/proposal-card.tsx api/resources/js/lib/reconstruct-session-messages.ts api/resources/js/components/__tests__/proposal-card.test.tsx
git commit -m "feat(ai): render expandable visual diff in proposal cards"
```

Expected: commit succeeds.

---

## Notes for the implementer

- The card lives in two surfaces (per-record AI sidebar and the `/ai` page) via the
  shared `AiChatPanel` → `ProposalCard`; both inherit the diff automatically.
- Live proposals get `tool` + full `human_diff` from `AgentTool::handle`; resumed ones
  from `AiSessionController` (`human_diff` at controller line 90, `tool` at line 89).
  `parseProposal` and the resume status-merge both pass these fields through unchanged,
  so no other plumbing is needed.
- Do not add a backend `rows` field or change any PHP — the normalization is
  intentionally frontend-side (spec "Out of scope").
