# Web Warm Theme + Dark Mode Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the public Atlas SPA (`web/`) with a warm "paper" palette and Fraunces serif headings, and add a first-class light/dark theme toggle where dark is a warm charcoal-brown.

**Architecture:** Theme is driven entirely by CSS custom properties in `web/src/styles.css` (light `:root` + `.dark`). A small zustand store (`web/src/lib/theme.ts`) is the single source of truth for the active theme — it toggles the `.dark` class on `<html>`, persists to `localStorage`, and all consumers (toggle button, map, timeline) share it. An inline pre-paint script in `index.html` prevents a flash of the wrong theme. The WebGL map and canvas timeline can't read CSS vars, so they re-derive colors from the active theme on change.

**Tech Stack:** React 19, Vite 7, Tailwind v4, shadcn, zustand 5 (already a dep), lucide-react, `@fontsource-variable/fraunces` (new), Vitest + jsdom.

## Global Constraints

- **Scope is `web/` only** — do NOT touch the Inertia admin app under `api/`.
- **Fonts must be free/self-hosted.** Use `@fontsource-variable/fraunces` for headings; keep `@fontsource-variable/geist` (body) and `@fontsource-variable/geist-mono`. Do NOT add commercial fonts (Louize/Manuka/Neue Montreal).
- **Keep the existing CSS token names and structure** in `styles.css` — only change values and add `--font-heading` + entity-accent values. Downstream components read these vars unchanged.
- **`localStorage` key is exactly `hm-theme`**, values `'light'` | `'dark'`.
- **Theme colors:** light paper `#faf9f6`, dark charcoal-brown `#2a2722` (never pitch black).
- **Two-state toggle only** (light ↔ dark). "System" is the initial default, not a third UI state.
- Run in the `web` service context; commands below are run from `web/` (host-side pnpm is fine for this workspace — the SPA runs host-side per project memory).
- After each task: `pnpm lint`, `pnpm types:check`, `pnpm build` must all pass.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `web/package.json` | add `@fontsource-variable/fraunces` |
| `web/src/styles.css` | Fraunces import; `--font-heading`; warm light/dark neutral tokens; re-tuned `--g-*` accents; `.dark .maplibregl-canvas` filter |
| `web/index.html` | pre-paint no-FOUC theme script + `theme-color` meta |
| `web/src/lib/theme.ts` | **new** — pure helpers (`resolveTheme`/`applyTheme`/…) + zustand `useTheme` store |
| `web/src/lib/theme.test.ts` | **new** — unit tests for helpers + store |
| `web/src/components/atlas/ThemeToggle.tsx` | **new** — Sun/Moon toggle button |
| `web/src/components/atlas/TopBar.tsx` | mount toggle; heading font on brand wordmark |
| `web/src/components/atlas/MobileTopBar.tsx` | mount toggle |
| `web/src/components/atlas/DetailPanel.tsx` | heading font on entity name (`h2`) |
| `web/src/lib/timeline/theme.ts` | warm light/dark canvas hex |
| `web/src/lib/map-icons.ts` | add `refreshGroupMarkers`; update hex fallbacks |
| `web/src/components/map/MapCanvas.tsx` | theme-aware label init + theme-reactive overlay effect; updated hex fallbacks |

---

## Task 1: Warm palette + Fraunces typography (light theme baseline)

Establishes the visual foundation: warm neutral tokens, re-tuned entity accents, the Fraunces heading font, and its application to the two most prominent titles. No toggle yet — the app renders in the new warm light theme. (CSS/visual work — no unit test; verified by build + visual check.)

**Files:**
- Modify: `web/package.json`
- Modify: `web/src/styles.css`
- Modify: `web/src/components/atlas/TopBar.tsx:41`
- Modify: `web/src/components/atlas/DetailPanel.tsx:229`

**Interfaces:**
- Produces: CSS token `--font-heading: 'Fraunces Variable', serif`; warm values for all existing `:root`/`.dark` tokens and `--g-*` accents (same names). Consumed by Tailwind classes `font-heading`, `bg-background`, `text-foreground`, etc., and by `groups.ts`/map/timeline (later tasks).

- [ ] **Step 1: Add the Fraunces dependency**

Run from `web/`:
```bash
pnpm add @fontsource-variable/fraunces
```
Expected: `package.json` gains `"@fontsource-variable/fraunces"` under dependencies; lockfile updates.

- [ ] **Step 2: Import Fraunces and set the heading font token in `styles.css`**

At the top of `web/src/styles.css`, add the Fraunces import alongside the existing font imports (after line 5, the geist-mono import):
```css
@import "@fontsource-variable/fraunces";
```

Then in the `@theme inline { … }` block, change the `--font-heading` line (currently `--font-heading: var(--font-sans);`) to:
```css
    --font-heading: 'Fraunces Variable', serif;
```
Leave `--font-sans` (Geist) and `--font-mono` unchanged.

- [ ] **Step 3: Replace the light `:root` neutral tokens with warm values**

In `web/src/styles.css`, replace the neutral values in the `:root { … }` block (lines ~72–94, the `--background` through `--radius`/`--chart-*` region) with these warm values. Keep every token name; keep `--radius: 0.625rem` and the sidebar tokens below unless listed:
```css
    --background: #faf9f6;
    --foreground: #2a2722;
    --card: #fdfcf9;
    --card-foreground: #2a2722;
    --popover: #fdfcf9;
    --popover-foreground: #2a2722;
    --primary: #2a2722;
    --primary-foreground: #faf9f6;
    --secondary: #f0ede6;
    --secondary-foreground: #2a2722;
    --muted: #f0ede6;
    --muted-foreground: #6f685f;
    --accent: #e9e3d8;
    --accent-foreground: #2a2722;
    --destructive: #b3402e;
    --border: #e6e1d8;
    --input: #e6e1d8;
    --ring: #b8ab97;
    --chart-1: #d8cfc0;
    --chart-2: #a89e8c;
    --chart-3: #8a7f6d;
    --chart-4: #6f6555;
    --chart-5: #4a4238;
```
Also warm the light sidebar tokens (lines ~96–103):
```css
    --sidebar: #f7f5f0;
    --sidebar-foreground: #2a2722;
    --sidebar-primary: #2a2722;
    --sidebar-primary-foreground: #faf9f6;
    --sidebar-accent: #e9e3d8;
    --sidebar-accent-foreground: #2a2722;
    --sidebar-border: #e6e1d8;
    --sidebar-ring: #b8ab97;
```

- [ ] **Step 4: Re-tune the light entity-group accents**

Replace the light entity-group block in `:root` (lines ~105–121, `--g-*` and `--map-*`) with the warm earthy palette:
```css
    /* Entity-group accents (warm cartographic) */
    --g-polity: #b4543f;
    --g-place: #6b7f4a;
    --g-event: #bd8a2c;
    --g-economy: #4d6a86;
    --g-culture: #8a5673;
    --g-polity-bg: #f6eae6;
    --g-place-bg: #eef0e4;
    --g-event-bg: #f6efdd;
    --g-economy-bg: #e6ecf1;
    --g-culture-bg: #f2e9ef;

    /* Basemap (warm parchment; currently unused by OHM style) */
    --map-water: #eceae4;
    --map-land: #e6e1d6;
    --map-coast: #cfc7b8;
    --map-grid: #e9e4d9;
```

- [ ] **Step 5: Replace the `.dark` block with the warm charcoal-brown palette**

Replace the neutral values in the `.dark { … }` block (lines ~124–173) with these. Keep token names:
```css
    --background: #2a2722;
    --foreground: #faf9f6;
    --card: #34302a;
    --card-foreground: #faf9f6;
    --popover: #34302a;
    --popover-foreground: #faf9f6;
    --primary: #faf9f6;
    --primary-foreground: #2a2722;
    --secondary: #3a362f;
    --secondary-foreground: #faf9f6;
    --muted: #3a362f;
    --muted-foreground: #a8a094;
    --accent: #423d35;
    --accent-foreground: #faf9f6;
    --destructive: #e0664f;
    --border: #423d35;
    --input: #4a443b;
    --ring: #6b6252;
    --chart-1: #d8cfc0;
    --chart-2: #a89e8c;
    --chart-3: #8a7f6d;
    --chart-4: #6f6555;
    --chart-5: #4a4238;
    --sidebar: #302c27;
    --sidebar-foreground: #faf9f6;
    --sidebar-primary: #faf9f6;
    --sidebar-primary-foreground: #2a2722;
    --sidebar-accent: #423d35;
    --sidebar-accent-foreground: #faf9f6;
    --sidebar-border: #423d35;
    --sidebar-ring: #6b6252;

    /* Entity-group accents (brightened for charcoal) */
    --g-polity: #d47a63;
    --g-place: #9cae6f;
    --g-event: #d9a94e;
    --g-economy: #7d9db8;
    --g-culture: #bb87a3;
    --g-polity-bg: #3a221b;
    --g-place-bg: #242a17;
    --g-event-bg: #332a14;
    --g-economy-bg: #1c2530;
    --g-culture-bg: #2c1f28;

    /* Basemap */
    --map-water: #1c1a17;
    --map-land: #24211c;
    --map-coast: #3a352d;
    --map-grid: #201e1a;
```

- [ ] **Step 6: Add the dark map-canvas filter to `styles.css`**

At the end of `web/src/styles.css` (after the `@layer base { … }` block), add:
```css
/* In dark mode the external OHM basemap stays light — dim it into the charcoal
   chrome. Targets only the WebGL canvas, so DOM controls stay crisp. */
.dark .maplibregl-canvas {
  filter: brightness(0.82) contrast(1.05) sepia(0.08);
}
```

- [ ] **Step 7: Apply the heading font to the TopBar brand wordmark**

In `web/src/components/atlas/TopBar.tsx`, line 41, change the brand `<span>` class from:
```tsx
        <span className="text-[15px] font-bold tracking-tight">History Mapped</span>
```
to:
```tsx
        <span className="font-heading text-[17px] font-semibold tracking-tight">
          History Mapped
        </span>
```

- [ ] **Step 8: Apply the heading font to the entity name in DetailPanel**

In `web/src/components/atlas/DetailPanel.tsx`, line 229, change:
```tsx
            <h2 className="mt-3 text-lg font-semibold leading-tight">{entity.name}</h2>
```
to:
```tsx
            <h2 className="mt-3 font-heading text-xl font-semibold leading-tight">
              {entity.name}
            </h2>
```

- [ ] **Step 9: Verify lint, types, and build**

Run from `web/`:
```bash
pnpm lint && pnpm types:check && pnpm build
```
Expected: all three pass with no errors.

- [ ] **Step 10: Visual check (manual)**

Run the SPA and confirm the light theme: `pnpm dev` (or the running stack at `:5173`). Expect a warm paper background, brown-black text, Fraunces serif on "History Mapped" and entity titles, and warmer entity badge colors. No dark toggle yet.

- [ ] **Step 11: Commit**

```bash
git add web/package.json web/pnpm-lock.yaml web/src/styles.css web/src/components/atlas/TopBar.tsx web/src/components/atlas/DetailPanel.tsx
git commit -m "feat(web): warm paper palette + Fraunces headings"
```
(If the lockfile lives at repo root, add the root lockfile path instead.)

---

## Task 2: Theme store, toggle, and no-FOUC script

Adds the shared theme state, the pre-paint script, and the toggle button. After this task, users can switch between the warm light and charcoal-dark themes and the choice persists with no flash on reload. This is the TDD task.

**Files:**
- Create: `web/src/lib/theme.ts`
- Create: `web/src/lib/theme.test.ts`
- Create: `web/src/components/atlas/ThemeToggle.tsx`
- Modify: `web/index.html`
- Modify: `web/src/components/atlas/TopBar.tsx`
- Modify: `web/src/components/atlas/MobileTopBar.tsx`

**Interfaces:**
- Produces:
  - `type Theme = 'light' | 'dark'`
  - `resolveTheme(): Theme` — stored explicit choice, else system.
  - `applyTheme(theme: Theme): void` — toggles `.dark` on `<html>`, updates `theme-color` meta.
  - `storeTheme(theme: Theme): void` / `storedTheme(): Theme | null` / `systemTheme(): Theme`
  - `useTheme` — a zustand store hook with state `{ theme: Theme; setTheme(t): void; toggle(): void }`, used as `useTheme((s) => s.theme)` and `useTheme.getState()`.
  - `ThemeToggle` — a React component (`{ className?: string }`).
- Consumes: warm tokens + `.dark` class from Task 1.

- [ ] **Step 1: Write the failing tests**

Create `web/src/lib/theme.test.ts`:
```ts
import { beforeEach, describe, expect, it, vi } from 'vitest';

const KEY = 'hm-theme';

/** jsdom lacks matchMedia — install a controllable stub. */
function setMatchMedia(dark: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: (query: string) => ({
      matches: dark,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  });
}

beforeEach(() => {
  vi.resetModules();
  localStorage.clear();
  document.documentElement.classList.remove('dark');
  if (!document.querySelector('meta[name="theme-color"]')) {
    const meta = document.createElement('meta');
    meta.setAttribute('name', 'theme-color');
    document.head.appendChild(meta);
  }
  setMatchMedia(false);
});

describe('resolveTheme', () => {
  it('prefers a stored explicit choice over the system preference', async () => {
    setMatchMedia(true); // system says dark
    localStorage.setItem(KEY, 'light');
    const { resolveTheme } = await import('./theme');
    expect(resolveTheme()).toBe('light');
  });

  it('falls back to the system preference when nothing is stored', async () => {
    setMatchMedia(true);
    const { resolveTheme } = await import('./theme');
    expect(resolveTheme()).toBe('dark');
  });
});

describe('applyTheme', () => {
  it('adds the dark class and sets theme-color for dark', async () => {
    const { applyTheme } = await import('./theme');
    applyTheme('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(
      document.querySelector('meta[name="theme-color"]')?.getAttribute('content'),
    ).toBe('#2a2722');
  });

  it('removes the dark class and sets theme-color for light', async () => {
    document.documentElement.classList.add('dark');
    const { applyTheme } = await import('./theme');
    applyTheme('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(
      document.querySelector('meta[name="theme-color"]')?.getAttribute('content'),
    ).toBe('#faf9f6');
  });
});

describe('useTheme store', () => {
  it('toggle flips the theme, applies the class, and persists', async () => {
    setMatchMedia(false); // start light
    const { useTheme } = await import('./theme');
    expect(useTheme.getState().theme).toBe('light');
    useTheme.getState().toggle();
    expect(useTheme.getState().theme).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(localStorage.getItem(KEY)).toBe('dark');
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `web/`:
```bash
pnpm exec vitest run src/lib/theme.test.ts
```
Expected: FAIL — cannot resolve module `./theme`.

- [ ] **Step 3: Implement `web/src/lib/theme.ts`**

Create `web/src/lib/theme.ts`:
```ts
/**
 * Theme (light/dark) source of truth for the Atlas SPA.
 *
 * A zustand store holds the active theme so every consumer — the toggle, the
 * map, the timeline — shares one value. `applyTheme` writes the `.dark` class on
 * <html> (which drives all CSS custom properties) and the browser theme-color.
 * The initial `.dark` class is set pre-paint by an inline script in index.html.
 */
import { create } from 'zustand';

export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'hm-theme';
const THEME_COLOR: Record<Theme, string> = { light: '#faf9f6', dark: '#2a2722' };

function prefersDark(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
  );
}

/** The OS-level preference. */
export function systemTheme(): Theme {
  return prefersDark() ? 'dark' : 'light';
}

/** The user's explicitly-stored choice, or null if they never chose. */
export function storedTheme(): Theme | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return v === 'light' || v === 'dark' ? v : null;
  } catch {
    return null;
  }
}

/** Explicit choice wins; otherwise follow the system. */
export function resolveTheme(): Theme {
  return storedTheme() ?? systemTheme();
}

/** Persist an explicit choice. */
export function storeTheme(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* ignore quota / privacy-mode errors */
  }
}

/** Reflect the theme onto the document (class + browser chrome color). */
export function applyTheme(theme: Theme): void {
  if (typeof document === 'undefined') return;
  document.documentElement.classList.toggle('dark', theme === 'dark');
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', THEME_COLOR[theme]);
}

interface ThemeState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggle: () => void;
}

export const useTheme = create<ThemeState>((set, get) => ({
  theme: resolveTheme(),
  setTheme: (theme) => {
    storeTheme(theme);
    applyTheme(theme);
    set({ theme });
  },
  toggle: () => {
    const next: Theme = get().theme === 'dark' ? 'light' : 'dark';
    storeTheme(next);
    applyTheme(next);
    set({ theme: next });
  },
}));

// Follow the OS preference until the user makes an explicit choice.
if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
  window
    .matchMedia('(prefers-color-scheme: dark)')
    .addEventListener('change', () => {
      if (storedTheme()) return;
      const next = systemTheme();
      applyTheme(next);
      useTheme.setState({ theme: next });
    });
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run from `web/`:
```bash
pnpm exec vitest run src/lib/theme.test.ts
```
Expected: PASS — all cases green.

- [ ] **Step 5: Add the no-FOUC script + theme-color meta to `index.html`**

In `web/index.html`, the `<head>` currently has `<meta name="theme-color" content="#ffffff" />`. Leave that meta (the script rewrites it), and add this inline script immediately AFTER the `<title>` line, before `</head>`:
```html
    <script>
      (function () {
        try {
          var t = localStorage.getItem('hm-theme');
          if (t !== 'light' && t !== 'dark') {
            t = window.matchMedia('(prefers-color-scheme: dark)').matches
              ? 'dark'
              : 'light';
          }
          if (t === 'dark') document.documentElement.classList.add('dark');
          var m = document.querySelector('meta[name="theme-color"]');
          if (m) m.setAttribute('content', t === 'dark' ? '#2a2722' : '#faf9f6');
        } catch (e) {}
      })();
    </script>
```

- [ ] **Step 6: Create the `ThemeToggle` component**

Create `web/src/components/atlas/ThemeToggle.tsx`:
```tsx
import { Moon, Sun } from 'lucide-react';
import { useTheme } from '@/lib/theme';
import { cn } from '@/lib/utils';

/** Two-state light/dark toggle. Shows the icon of the theme it switches TO. */
export function ThemeToggle({ className }: { className?: string }) {
  const theme = useTheme((s) => s.theme);
  const toggle = useTheme((s) => s.toggle);
  const dark = theme === 'dark';
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
      className={cn(
        'grid size-9 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
        className,
      )}
    >
      {dark ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}
```

- [ ] **Step 7: Mount the toggle in the desktop TopBar**

In `web/src/components/atlas/TopBar.tsx`, add the import at the top (with the other component imports):
```tsx
import { ThemeToggle } from '@/components/atlas/ThemeToggle';
```
Then in the right-hand tools cluster (the `<div className="flex items-center gap-2">` around line 60), add `<ThemeToggle />` right before the Settings button:
```tsx
        <ViewToggle />
        <ThemeToggle />
        <button
          type="button"
          className="grid size-9 place-items-center rounded-lg text-muted-foreground hover:bg-muted"
          aria-label="Layers"
        >
          <Layers size={16} />
        </button>
```

- [ ] **Step 8: Mount the toggle in the MobileTopBar**

In `web/src/components/atlas/MobileTopBar.tsx`, add the import:
```tsx
import { ThemeToggle } from '@/components/atlas/ThemeToggle';
```
Then add `<ThemeToggle />` between the search pill button and the Tools button (before the `<button … aria-label="Tools">`):
```tsx
      <ThemeToggle className="flex-none border bg-card" />
      <button
        type="button"
        onClick={() => setTools((v) => !v)}
        aria-label="Tools"
```

- [ ] **Step 9: Verify lint, types, tests, and build**

Run from `web/`:
```bash
pnpm lint && pnpm types:check && pnpm exec vitest run && pnpm build
```
Expected: all pass.

- [ ] **Step 10: Visual check (manual)**

Run the SPA. Confirm: the toggle appears in both desktop and mobile headers; clicking it flips the whole UI between warm paper and charcoal-brown; a full page reload keeps the chosen theme with NO flash of the wrong colors.

- [ ] **Step 11: Commit**

```bash
git add web/src/lib/theme.ts web/src/lib/theme.test.ts web/src/components/atlas/ThemeToggle.tsx web/index.html web/src/components/atlas/TopBar.tsx web/src/components/atlas/MobileTopBar.tsx
git commit -m "feat(web): light/dark theme store, toggle, and no-flash boot"
```

---

## Task 3: Map & timeline follow the theme

Makes the WebGL map overlays, group markers, and the canvas timeline re-derive their colors when the theme changes (they can't read CSS vars), and correctly initialize when the app boots in dark mode.

**Files:**
- Modify: `web/src/lib/timeline/theme.ts`
- Modify: `web/src/lib/map-icons.ts`
- Modify: `web/src/components/map/MapCanvas.tsx`

**Interfaces:**
- Consumes: `useTheme` from `@/lib/theme` (Task 2); warm `--g-*` accents (Task 1).
- Produces: `refreshGroupMarkers(map): Promise<void>` in `map-icons.ts`.

- [ ] **Step 1: Update the timeline canvas colors to warm values**

In `web/src/lib/timeline/theme.ts`, update the four color helpers to the warm palette. Replace their return expressions:
```ts
/** Readable text colour for canvas labels in the active theme. */
export function labelTextColor(): string {
  return isDarkTheme() ? '#faf9f6' : '#2a2722';
}

/** Contrasting outline colour so labels stay legible over coloured spans. */
export function labelOutlineColor(): string {
  return isDarkTheme() ? '#2a2722' : '#faf9f6';
}

/** Muted colour for time-axis tick labels (approximates --muted-foreground). */
export function axisLabelColor(): string {
  return isDarkTheme() ? '#a8a094' : '#6f685f';
}

/** Subtle colour for the axis line and ticks (approximates --border). */
export function axisLineColor(): string {
  return isDarkTheme() ? '#423d35' : '#e6e1d8';
}
```
Leave `APP_FONT_FAMILY` (Geist) and `isDarkTheme()` unchanged.

- [ ] **Step 2: Add `refreshGroupMarkers` and update fallbacks in `map-icons.ts`**

In `web/src/lib/map-icons.ts`, update the hex fallbacks in `groupColors()` to match the new light accents:
```ts
  return {
    POLITY: c('--g-polity', '#b4543f'),
    PLACE: c('--g-place', '#6b7f4a'),
    EVENT: c('--g-event', '#bd8a2c'),
    ECONOMY: c('--g-economy', '#4d6a86'),
    CULTURE: c('--g-culture', '#8a5673'),
    DEFAULT: '#71717a',
  };
```
Then append a `refreshGroupMarkers` export at the end of the file (after `registerGroupMarkers`):
```ts
/**
 * Re-render every group marker for the current theme. Removes the cached images
 * (which `registerGroupMarkers` would otherwise skip) then re-registers them, so
 * a theme toggle recolors the point icons.
 */
export async function refreshGroupMarkers(map: MapLibreMap): Promise<void> {
  const ids = [
    ...Object.keys(GROUP_GLYPHS).map((g) => markerImageId(g)),
    'marker-DEFAULT',
  ];
  for (const id of ids) {
    if (map.hasImage(id)) map.removeImage(id);
  }
  await registerGroupMarkers(map);
}
```

- [ ] **Step 3: Make MapCanvas theme-aware on init and update fallbacks**

In `web/src/components/map/MapCanvas.tsx`:

(a) Add imports — extend the `map-icons` import and add the theme hook:
```tsx
import { registerGroupMarkers, refreshGroupMarkers } from '@/lib/map-icons';
```
and near the other `@/…` imports:
```tsx
import { useTheme } from '@/lib/theme';
```

(b) Update the hex fallbacks in `groupColorExpression()` to the new light accents:
```tsx
    'POLITY', c('--g-polity', '#b4543f'),
    'PLACE', c('--g-place', '#6b7f4a'),
    'EVENT', c('--g-event', '#bd8a2c'),
    'ECONOMY', c('--g-economy', '#4d6a86'),
    'CULTURE', c('--g-culture', '#8a5673'),
```

(c) Make the initial symbol label colors theme-aware. Replace the `paint` block of the `SYMBOL_LAYER` `addLayer` call (currently `'text-color': '#1b1b1b'`, `'text-halo-color': '#ffffff'`) with:
```tsx
          paint: {
            'text-color': document.documentElement.classList.contains('dark')
              ? '#faf9f6'
              : '#2a2722',
            'text-halo-color': document.documentElement.classList.contains('dark')
              ? '#2a2722'
              : '#ffffff',
            'text-halo-width': 1.4,
          },
```

- [ ] **Step 4: Add the theme-reactive effect to MapCanvas**

In `web/src/components/map/MapCanvas.tsx`, read the theme inside the component (near the other hooks, e.g. after `const { data } = useEntitiesInView();`):
```tsx
  const theme = useTheme((s) => s.theme);
```
Then add a new effect after the existing "push entity data" effect (after the `}, [data]);` block, before `return`):
```tsx
  // ── recolor overlays when the theme changes (WebGL can't read CSS vars) ─────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const groupColor = groupColorExpression();
    if (map.getLayer(FILL_LAYER)) {
      map.setPaintProperty(FILL_LAYER, 'fill-color', groupColor);
    }
    if (map.getLayer(LINE_LAYER)) {
      map.setPaintProperty(LINE_LAYER, 'line-color', groupColor);
    }
    if (map.getLayer(SYMBOL_LAYER)) {
      const dark = theme === 'dark';
      map.setPaintProperty(SYMBOL_LAYER, 'text-color', dark ? '#faf9f6' : '#2a2722');
      map.setPaintProperty(
        SYMBOL_LAYER,
        'text-halo-color',
        dark ? '#2a2722' : '#ffffff',
      );
    }
    void refreshGroupMarkers(map);
  }, [theme]);
```

- [ ] **Step 5: Verify lint, types, tests, and build**

Run from `web/`:
```bash
pnpm lint && pnpm types:check && pnpm exec vitest run && pnpm build
```
Expected: all pass. (If eslint flags the mount-once init effect's deps, it is already suppressed with the existing `eslint-disable-next-line react-hooks/exhaustive-deps`; the new `[theme]` effect needs no suppression.)

- [ ] **Step 6: Visual check (manual)**

Run the SPA. Toggle to dark and confirm: entity fills/outlines and point markers recolor to the brightened accents; symbol labels are light with a dark halo; the timeline axis/labels are warm and legible; the OHM basemap dims via the CSS filter so it recedes into the charcoal chrome. Toggle back to light and confirm everything returns to the paper palette. Reload in dark mode and confirm map labels start correct (no need to toggle).

- [ ] **Step 7: Commit**

```bash
git add web/src/lib/timeline/theme.ts web/src/lib/map-icons.ts web/src/components/map/MapCanvas.tsx
git commit -m "feat(web): map overlays, markers, and timeline follow the theme"
```

---

## Self-Review Notes

- **Spec coverage:** §1 typography → Task 1 (steps 1–2, 7–8). §2 warm palette → Task 1 (steps 3, 5). §3 entity accents → Task 1 (steps 4, 5) + Task 3 fallbacks. §4 toggle/no-FOUC → Task 2. §5 map/timeline reactivity → Task 3. §5 dark basemap filter → Task 1 (step 6). §6 testing → Task 2 unit tests + per-task lint/types/build/visual.
- **Type consistency:** `useTheme` used identically as `useTheme((s) => s.theme)` / `useTheme.getState()` in ThemeToggle, MapCanvas, and tests. `refreshGroupMarkers(map)` defined in Task 3 step 2, called in step 4. `applyTheme`/`resolveTheme`/`storeTheme` signatures match tests.
- **Accent fallbacks** are duplicated in three places by necessity (WebGL/SVG can't read CSS vars): `map-icons.ts` `groupColors()`, MapCanvas `groupColorExpression()`, and the CSS vars — all set to the same light values in Task 1 & 3.
