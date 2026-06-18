# Mobile-responsive Atlas shell — bottom drawer

**Date:** 2026-06-19
**Status:** Approved (design); pending implementation plan
**Surface:** `web/` (public Atlas SPA, React 19 + Vite)
**Related:** [`2026-06-13-atlas-frontend-plumbing-design.md`](2026-06-13-atlas-frontend-plumbing-design.md) (the "spec §" the code comments reference), `web/public/wf-mobile.jsx` / `wf-screens.jsx` (wireframes)

## Problem

The Atlas SPA is desktop-only. The shell ([`web/src/app/routes/AtlasLayout.tsx`](../../../web/src/app/routes/AtlasLayout.tsx)) floats a fixed-width **left sidebar** (340px Browse/Chronicles list, collapsible to a 52px rail) and a **right panel** (entity detail *or* chronicle player, 380px) over a full-bleed map, with a `Timeline` spine beneath. Below ~768px those fixed panels cover the map and there is no touch-appropriate way to browse, inspect, or scrub.

The frontend plumbing spec already anticipated this: the ephemeral store carries `sheet: 'peek' | 'half' | 'full'` with `setSheet`, exposed via `useSheet()` ([`web/src/stores/ephemeral.ts`](../../../web/src/stores/ephemeral.ts), [`web/src/hooks/ephemeral.ts`](../../../web/src/hooks/ephemeral.ts)). That state is currently unconsumed — no breakpoint logic and no drawer exist. **This work finishes the planned-but-unbuilt mobile shell.**

## Goals

- Below the `md` breakpoint (`max-width: 767px`), present a touch-first shell where a **single bottom sheet** replaces both the left sidebar and the right panel.
- The sheet has three drag/snap states — **peek** (list teaser), **half** (scrollable list), **full** (entity detail / chronicle) — wired to the existing `sheet` store.
- Adapt the top bar and timeline for small screens (full mobile shell, not just a bolted-on drawer).
- Reuse existing content components; no behavior change on desktop.

## Non-goals

- Globe-view mobile tuning, landscape-phone special-casing, offline support.
- Reworking the timeline's scrub internals (only a compact visual variant).
- Tablet-specific layout beyond the single `md` switch.

## Decisions (locked with stakeholder)

| Decision | Choice |
|---|---|
| Drawer scope | **One sheet** hosting list (half) ↔ entity detail (full); snap states swap content |
| Breakpoint | **`md`** — mobile shell below `max-width: 767px` |
| Sheet mechanism | **vaul** (purpose-built React bottom sheet: drag, snap points, momentum, a11y) |
| Mobile shell | **Full** — compact top bar + slim floating timeline + drawer |
| Shell selection | **Render-branch** on a media-query hook (Approach A) |

## Design language (frontend-design pass)

The Atlas has an established, deliberate identity; the task is to translate it to touch, not reinvent it.

- **Type:** Geist Variable (sans) + Geist Mono. Mono is reserved for *data* — years, counts, coordinates. This convention is preserved everywhere in the mobile shell.
- **Color:** oklch neutrals + the five muted-cartographic group accents (polity terracotta, place teal, event ochre, economy blue, culture violet). No new colors introduced.
- **Layout principle:** the map is the whole screen; everything else floats *over* it as quiet `card` surfaces (mirrors the desktop rule that the map never resizes).
- **Signature element:** the **"Within view" peek** — the collapsed sheet is a live, scope-aware readout of what is on the map *right now* (current viewport × current year), with group-color chips and a mono count. Boldness is spent here; everything else stays disciplined.
- **The one risk:** the sheet is **persistent, non-dismissible** (always at least peek) and **non-modal** (no scrim; the map stays pannable behind it). It behaves like a fixed instrument panel rather than a typical modal sheet — appropriate for a map app and a fit for the pre-designed `peek/half/full` states.

## Architecture — Approach A (render-branch)

`AtlasLayout` chooses one of two shells via a new `useIsMobile()` hook (`matchMedia('(max-width: 767px)')`, listener-based). Only one shell mounts at a time, so vaul and the 340px sidebar never coexist in the DOM. The `MapCanvas` mounts once and is shared.

```
AtlasLayout
├─ useIsMobile() === false → <DesktopShell>   (today's layout, lifted verbatim)
│     TopBar · MapCanvas · LeftSidebar · RightPanel · Timeline · CommandPalette
└─ useIsMobile() === true  → <MobileShell>
      MobileTopBar · MapCanvas · MobileTimeline · MobileSheet · CommandPalette
```

**Alternatives rejected:** *(B)* CSS-only `md:` toggling in one shell — vaul needs JS state regardless and both heavy trees would mount; *(C)* additive sheet over the unchanged desktop chrome — that is the "drawer only" scope the stakeholder declined.

## Mobile shell layout

```
PEEK ~130px               HALF ~55%                  FULL ~95%
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ ◎ Search…     ⚙ │   │ ◎ Search…     ⚙ │   │ ‹ Results   ⭐ ↗ │
│ ┌──────────────┐ │   │  (map, pin focus)│   │ ● EVENT          │
│ │490BCE ─●─ ▶│ │   ├═════ grab ══════┤   │ Battle of Marathon│
│ └──────────────┘ │   │ Filter…      [⌕]│   │ ⌚490BCE 📍Marathon│
│   (full map)     │   │ [polity][place]… │   ├──────────────────┤
├═════ grab ══════┤   │ ● Achaemenid     │   │ Began… Type…     │
│ Within view  248 │   │ ● Marathon     › │   │ ── Overview ──   │
│ [polity][place]… │   │ ● Attica         │   │ ── Relationships─│
│ ● Marathon       │   │ ● Delian League  │   │ │● Athens ●Persia│
└──────────────────┘   └──────────────────┘   └──────────────────┘
```

- **MobileTopBar:** compass mark · full-width search pill (opens existing `CommandPalette` via `useCommandPalette().setOpen(true)`) · one tools button → popover for View (Map/Globe), Layers, Settings. Year-nav arrows are dropped on mobile (scrub the timeline instead).
- **MobileTimeline:** compact single-row card pinned at top, over the map — mono year + era, draggable track, play. A slim variant of `Timeline` (drops zoom buttons and tick density). May be implemented as a `compact` prop on `Timeline` or a separate component; the plan decides.
- **MobileSheet:** one vaul `Drawer`, `snapPoints={['130px', 0.55, 0.97]}`, `modal={false}`, `dismissible={false}`, controlled by `useSheet()`. Content swaps by state (see below).

## Content-sharing refactor

Separate **chrome from content** so the desktop aside and the mobile sheet share one source of truth:

- `DetailPanel` → extract `DetailPanelContent` (title block, stats, summary, relationships timeline). Desktop keeps its `<aside>` wrapper + close bar; the sheet's *full* state renders the same content under a "‹ Results" bar.
- `ChroniclePlayer` → same split into `ChroniclePlayerContent`.
- `BrowseTab` / `ChronicleList` are already chrome-less and are reused directly. The mobile sheet supplies its own tab strip (mirroring the tab strip in `LeftSidebar`).

Desktop renders the identical content, wrapped exactly as before — **no desktop behavior change**.

## State & behavior

- Reuse the existing `sheet` store + `useSheet()`. **No new global state.**
- **Content selection in the sheet** (priority order): chronicle active (`useChronicleNav().isActive`) → `ChroniclePlayerContent`; else selection set (`useSelection().sel`) → `DetailPanelContent`; else → Browse/Chronicles tabs.
- **Selection drives height:**
  - List row tap → sheet animates to `full` (detail).
  - Map pin tap → selects and lands at `half` first (keeps map context), user can drag to `full`.
  - "‹ Results" / clearing `sel` → returns to `half` (list).
- vaul's `activeSnapPoint` is bound two-way to the `sheet` value, so grabber-drag and programmatic changes stay in sync.
- `CommandPalette` (⌘K / search pill) is unchanged and shared by both shells.

## New / changed files (indicative)

- **New:** `web/src/hooks/useMediaQuery.ts` (exporting `useIsMobile`); `web/src/components/atlas/MobileShell.tsx`, `MobileTopBar.tsx`, `MobileSheet.tsx`, `MobileTimeline.tsx`; `web/src/components/atlas/DesktopShell.tsx` (today's `AtlasLayout` body, lifted verbatim).
- **Changed:** `AtlasLayout.tsx` (render-branch); `DetailPanel.tsx` and `ChroniclePlayer.tsx` (extract content components).
- **Dependency:** add `vaul` (`^1.1.x`, React 19-compatible — verify the version resolves at install).

## Testing

- **Vitest:** `useIsMobile` (matchMedia listener add/remove, boundary at 767/768px) and the sheet content-selection logic (chronicle > selection > list precedence; selection→height transitions).
- **Manual / Playwright:** 390×844 (iPhone) and the 768px boundary — peek/half/full drag, map-tap → half, list-tap → full, back → half, search pill opens palette.
- Preview runs host-side from this worktree (`web/` Vite); no Docker bind-mount dependency.

## Risks & mitigations

- **vaul ↔ React 19 / non-modal + snap points + non-dismissible:** a supported but less-common vaul combination. Mitigation: pin a known-good version at install; if a blocker surfaces, fall back to the "custom @base-ui sheet" mechanism without changing the rest of the design.
- **vaul pulls a Radix dialog transitive dep** (app otherwise uses `@base-ui/react`): acceptable, self-contained to the sheet.
- **Two-way snap-point sync** can loop if naive. Mitigation: treat the store as the single source of truth and guard echo updates.
