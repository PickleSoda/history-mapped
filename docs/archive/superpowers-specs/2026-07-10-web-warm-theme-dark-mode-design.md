# Web Atlas — Warm "Paper" Theme + Dark Mode Toggle

**Date:** 2026-07-10
**Surface:** `web/` (standalone React 19 + Vite public Atlas SPA) only. The Inertia admin app under `api/` is **out of scope**.
**Status:** Design approved, pending implementation plan.

## Goal

Restyle the public Atlas SPA with a warmer, editorial "paper" aesthetic inspired by
[henry.codes](https://henry.codes/writing/a-website-to-destroy-all-websites/), and add a
first-class light/dark theme toggle. Dark mode is a warm **charcoal-brown** (henry's `#2a2722`),
deliberately **not** pitch black.

The reference site's character comes from three things we reproduce with free, self-hostable
substitutes:

1. A warm literary **serif for headings** (reference uses the commercial *Louize*; we use **Fraunces**).
2. A warm **paper background + brown-black text** rather than pure white/black.
3. Generous, editorial type treatment.

The reference's commercial fonts (Louize, Manuka, PP Neue Montreal) are **not** bundled — no license.

## Current state (what exists today)

- **Styling:** Tailwind v4 + shadcn, theme via CSS custom properties in
  [`web/src/styles.css`](../../../web/src/styles.css). Neutral grayscale `oklch` palette.
- **Fonts:** `@fontsource-variable/geist` + `@fontsource-variable/geist-mono`. `--font-heading`
  is currently just an alias of `--font-sans`.
- **Dark mode:** A `.dark` block already exists in `styles.css`, **but nothing toggles it** —
  there is no theme store, hook, or toggle UI. The `.dark` styles are effectively dormant.
- **Entity accents:** Five semantic group colors (`--g-polity/place/event/economy/culture`,
  each with a `-bg` soft tint) defined per light/dark, consumed via CSS vars in
  [`web/src/lib/groups.ts`](../../../web/src/lib/groups.ts).
- **Map:** [`MapCanvas.tsx`](../../../web/src/components/map/MapCanvas.tsx) renders an external,
  **light-only** OpenHistoricalMap basemap (`main.json` fetched at runtime). Our entity overlay
  layers read the `--g-*` vars **once at map init** via `getComputedStyle`
  (`groupColorExpression()`); symbol label colors are hardcoded (`#1b1b1b` text / `#ffffff` halo).
  Group marker icons are generated from the same vars at registration time in
  [`map-icons.ts`](../../../web/src/lib/map-icons.ts).
- **Timeline:** [`lib/timeline/theme.ts`](../../../web/src/lib/timeline/theme.ts) draws on a
  `<canvas>` where CSS vars don't resolve, so it derives **hardcoded hex** per light/dark, keyed
  off `document.documentElement.classList.contains('dark')`.
- **The `--map-water/land/coast/grid` vars in `styles.css` are defined but unused** (grep finds no
  consumer) — the basemap is OHM's external style. They can be updated for consistency but drive nothing.

## Design

### 1. Typography

- Add dependency `@fontsource-variable/fraunces` (free, OFL, self-hosted variable font). Keep Geist
  + Geist Mono.
- In `styles.css`: import Fraunces; set `--font-heading: 'Fraunces Variable', serif;` (no longer an
  alias of `--font-sans`). `--font-sans` (Geist) and `--font-mono` unchanged.
- Enable Fraunces optical sizing and a small softness via `font-variation-settings`
  (`opsz` auto/large, a touch of `SOFT`; `WONK` off) on heading elements.
- Apply `font-heading` to prominent titles only — a **light-touch** pass, not wholesale markup change:
  - TopBar brand/wordmark
  - `DetailPanel` entity name + section headers
  - `NavBreadcrumb`
  - Mobile sheet titles (`SheetContent` / `MobileSheet`)
  - A base rule for bare `h1, h2, h3`
  Body text, labels, badges, and controls stay Geist.

### 2. Warm color palette

Replace the neutral grayscale values with warm, low-chroma equivalents (hue ≈ 70–90, amber/brown),
keeping the **exact same token names and structure** so downstream components need no changes.

**Light — "paper":**
- `--background`: warm off-white (~`#faf9f6`)
- `--foreground`: warm brown-black (~`#2a2722`, henry's text color)
- `--card`, `--popover`: warm near-white
- `--muted`, `--secondary`, `--accent`: warm light beige
- `--muted-foreground`: warm mid-gray (~`#6b6560`)
- `--border`, `--input`: warm low-contrast neutral (~`#e7e3dc`)
- `--primary`: brown-black; `--primary-foreground`: paper
- `--ring`: warm mid tone

**Dark — "charcoal-brown":**
- `--background`: ≈ `#2a2722` (henry's dark bg — warm charcoal, not pitch black)
- `--card`, `--popover`: one step lighter "echo" (~`#33302b`)
- `--foreground`: warm off-white (~`#faf9f6`)
- `--muted-foreground`: warm light-gray (~`#a19a90`)
- `--border`, `--input`: warm, low-contrast (translucent warm white or ~`hsl(38 11% 25%)`)
- `--primary`: warm off-white; `--primary-foreground`: charcoal

Values may be authored in `oklch` (consistent with the current file) or hex; the requirement is the
warm hue + low chroma + the light/dark relationships above. `--destructive` stays a warm red;
`--chart-*` re-tuned to warm neutrals.

### 3. Entity-group accents — re-tuned earthy palette

Keep the five semantic identities but move them into a harmonious, muted cartographic set that reads
well over both paper and charcoal, while remaining five-way distinguishable. Each group keeps its
`--g-<name>` accent, brightened `.dark` variant, and `--g-<name>-bg` soft tint.

| Group    | Identity           | Direction (light)                         |
|----------|--------------------|-------------------------------------------|
| polity   | terracotta / rust  | keep ~`#b4543f`, harmonized               |
| place    | sage / olive green | warm the current teal toward olive-green  |
| event    | gold / amber       | warm gold ~`#c08a2e`                       |
| economy  | dusty slate-blue   | keep a muted blue for hue separation (desaturated, cooler anchor) |
| culture  | warm plum / mauve  | warm the current purple toward plum        |

Soft `-bg` tints: very light warm tint on paper; deep low-chroma tint on charcoal. Dark accents
brightened for contrast against `#2a2722`. Because `groups.ts` and detail/badge components read the
CSS vars, they update automatically; the map/markers reactivity is handled in §5.

### 4. Dark mode toggle (new)

- **`web/src/lib/theme.ts`** — the single source of truth:
  - Type `Theme = 'light' | 'dark'`.
  - Reads persisted choice from `localStorage['hm-theme']`; if absent, resolves the **system**
    default via `matchMedia('(prefers-color-scheme: dark)')`.
  - `applyTheme(theme)` toggles the `.dark` class on `document.documentElement` and updates the
    `<meta name="theme-color">` content (paper vs charcoal).
  - `useTheme()` hook returns `{ theme, setTheme, toggle }`, persisting to `localStorage` on change.
    While no explicit choice is stored, it tracks system changes via a `matchMedia` listener; once
    the user toggles, the explicit choice wins and persists.
- **`index.html`** — a tiny **inline** script in `<head>`, before the app bundle, reads
  `localStorage['hm-theme']`/system and sets `.dark` **pre-paint** to avoid a flash of the wrong
  theme (FOUC). Keep it dependency-free and minimal.
- **`ThemeToggle` component** (`web/src/components/atlas/ThemeToggle.tsx`) — a button using lucide
  `Sun`/`Moon`, wired to `useTheme().toggle`, accessible label. Reuses the existing `ui/button`.
- **Placement:** in [`TopBar.tsx`](../../../web/src/components/atlas/TopBar.tsx) (desktop) and
  [`MobileTopBar.tsx`](../../../web/src/components/atlas/MobileTopBar.tsx) (mobile).
- Two-state toggle (light ↔ dark). "System" is only the initial default, not a third UI state.

### 5. Map & timeline follow the theme

- **Timeline** (`lib/timeline/theme.ts`): update the hardcoded light/dark hex
  (`labelTextColor`, `labelOutlineColor`, `axisLabelColor`, `axisLineColor`) to the new warm values.
  It already keys off the `.dark` class and re-renders; no structural change.
- **Map** (`MapCanvas.tsx` + `map-icons.ts`): make the overlay theme-reactive on toggle. Add an
  effect keyed on the active theme that, when the map/style is loaded:
  - re-applies `groupColorExpression()` to `entities-fill` (`fill-color`) and `entities-line`
    (`line-color`) via `setPaintProperty`;
  - flips the `entities-symbols` label paint — dark: light text (`#faf9f6`) + dark halo
    (`#2a2722`); light: current dark text + light halo;
  - re-registers group markers so their icon colors match the re-tuned/brightened accents.
  Hardcoded hex fallbacks in `groupColorExpression()` updated to the new accent values.
- **OHM basemap** (dark mode): the external basemap stays OHM's cartography. Apply a CSS filter to
  the map canvas container in `.dark` (`filter: brightness(.82) contrast(1.05) sepia(.08)`) so the
  bright map recedes into the charcoal chrome. No external style swap; OHM historical layers intact.
  - **Known limitation (accepted):** the basemap is not a true dark cartography — the filter is a
    pragmatic softening, not a redesign. A genuine dark basemap is explicitly out of scope.

### 6. Testing & verification

- **Unit (Vitest):** `web/src/lib/theme.test.ts` — resolver precedence (explicit storage > system),
  `applyTheme` toggles `.dark` and updates `theme-color`, `toggle` flips and persists. Mock
  `localStorage` + `matchMedia`.
- **Checks:** `pnpm lint`, `pnpm types:check`, `pnpm build` all green.
- **Visual verification:** run the SPA (`:5173`), confirm in both themes: no FOUC on reload,
  toggle flips chrome + panels + badges + timeline + map overlays, dark map filter reads well,
  Fraunces headings render, entity accents remain distinguishable on both backgrounds.

## Files touched (anticipated)

| File | Change |
|------|--------|
| `web/package.json` | add `@fontsource-variable/fraunces` |
| `web/src/styles.css` | import Fraunces; warm light/dark tokens; re-tuned `--g-*` accents; `--font-heading`; map-canvas dark filter |
| `web/index.html` | pre-paint no-FOUC theme script; `theme-color` meta |
| `web/src/lib/theme.ts` | **new** — resolver, `applyTheme`, `useTheme` |
| `web/src/lib/theme.test.ts` | **new** — unit tests |
| `web/src/components/atlas/ThemeToggle.tsx` | **new** — toggle button |
| `web/src/components/atlas/TopBar.tsx` | mount toggle; heading font on brand |
| `web/src/components/atlas/MobileTopBar.tsx` | mount toggle |
| `web/src/components/atlas/DetailPanel.tsx` | heading font on title/section headers |
| `web/src/components/atlas/NavBreadcrumb.tsx` | heading font (as appropriate) |
| `web/src/components/atlas/SheetContent.tsx` / `MobileSheet.tsx` | heading font on titles |
| `web/src/lib/timeline/theme.ts` | warm light/dark hex |
| `web/src/components/map/MapCanvas.tsx` | theme-reactive overlay effect; updated fallbacks/label paint |
| `web/src/lib/map-icons.ts` | re-register markers on theme change (if needed) |

## Non-goals

- No changes to the Inertia admin app (`api/`).
- No genuine dark OHM basemap / external style swap.
- No new third UI state for "system" (initial default only).
- No restructuring of the map init lifecycle beyond adding the theme-reactive effect.
