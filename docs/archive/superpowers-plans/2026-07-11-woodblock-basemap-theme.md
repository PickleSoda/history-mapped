# Woodblock Basemap with Theme-Aware Recoloring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Outcome (2026-07-11): scrapped** — see the spec header note; only a URL-only style switch shipped.

**Goal:** Replace the OHM "main" basemap with OHM's woodblock style in both themes, with a runtime charcoal+cream dark recoloring (and remove the CSS dim-filter hack).

**Architecture:** The woodblock style JSON is fetched once through the existing `loadHistoricalBasemapStyle()` normalization. A new pure module `basemap-theme.ts` builds a per-layer paint table mapping every color-bearing paint property (plain strings AND colors nested in expressions) to `{ light: original, dark: transformed }`, and maps every `*-pattern` paint property to `{ light: original, dark: null }` (patterns override colors in MapLibre, and the paper/road-ink sprites can't be tinted — dark mode clears them so flat colors render). Symbol layers with sprite icons get a synthetic `icon-opacity` entry (`dark: 0`) so ink-drawn icons don't vanish-glow on dark while their text labels keep working. `applyBasemapTheme()` flips paints with `setPaintProperty` — the same mechanism the entity overlays already use; no `setStyle`, no reload.

**Tech Stack:** React 19, MapLibre GL 5, Vite 7, Vitest (jsdom), TypeScript.

## Global Constraints

- Scope is `web/` only. No `api/` changes.
- Woodblock style URL exactly: `https://www.openhistoricalmap.org/map-styles/woodblock/woodblock.json`. Fallback style URL unchanged.
- Dark palette anchors (from spec): background/water `#221f1b`, land `#353028`, admin boundaries `#cfb37d`, road fills `#6f6555`, city label text `#e8ddc4`, label halos `#2a2722`.
- The existing normalization pipeline (English labels, icon stripping, wikidata exclusion, runtime date filter) must remain untouched and continue to apply.
- The `.dark .maplibregl-canvas` CSS filter must be REMOVED (superseded).
- Entity overlay layers (`entities-fill`, `entities-line`, `entities-symbols`) and group markers are already theme-reactive — do not touch their logic.
- After each task: `pnpm lint && pnpm types:check && pnpm exec vitest run && pnpm build` all pass (run from `web/`, host-side). Baseline: 48 tests, 2 pre-existing lint warnings in `CommandPalette.tsx`.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `web/src/lib/basemap-theme.ts` | **new** — dark color lookup, fallback darkener, paint-table builder, theme applier |
| `web/src/lib/basemap-theme.test.ts` | **new** — unit tests for all pure functions + fake-map applier test |
| `web/src/lib/map-config.ts` | switch `OHM_STYLE_URL` to woodblock |
| `web/src/components/map/MapCanvas.tsx` | build table at style load; apply on boot-in-dark; apply in the `[theme]` effect |
| `web/src/styles.css` | remove the `.dark .maplibregl-canvas` filter rule |

---

### Task 1: `basemap-theme.ts` — pure recoloring module (TDD)

**Files:**
- Create: `web/src/lib/basemap-theme.ts`
- Test: `web/src/lib/basemap-theme.test.ts`

**Interfaces:**
- Consumes: nothing from other tasks. `StyleSpecification` type from `maplibre-gl`.
- Produces (Task 2 relies on these exact signatures):
  - `type BasemapPaintTable = Record<string, Record<string, { light: unknown; dark: unknown }>>`
  - `buildBasemapPaintTable(style: StyleSpecification): BasemapPaintTable`
  - `applyBasemapTheme(map: MapLibreThemable, theme: 'light' | 'dark', table: BasemapPaintTable): void` where `MapLibreThemable = Pick<maplibregl.Map, 'getLayer' | 'setPaintProperty'>`
  - `darkColorFor(color: string): string` (exported for tests)

- [ ] **Step 1: Write the failing tests**

Create `web/src/lib/basemap-theme.test.ts`:

```ts
import { describe, expect, it, vi } from 'vitest';
import type { StyleSpecification } from 'maplibre-gl';
import {
  applyBasemapTheme,
  buildBasemapPaintTable,
  darkColorFor,
} from './basemap-theme';

/** Minimal style wrapper for table-builder tests. */
function styleWith(layers: unknown[]): StyleSpecification {
  return {
    version: 8,
    sources: {},
    layers,
  } as unknown as StyleSpecification;
}

describe('darkColorFor', () => {
  it('maps known woodblock colors via the explicit lookup', () => {
    expect(darkColorFor('rgba(207, 179, 125, 1)')).toBe('#221f1b'); // paper/water
    expect(darkColorFor('rgba(236, 225, 203, 1)')).toBe('#353028'); // land
    expect(darkColorFor('rgba(157, 169, 174, 1)')).toBe('#cfb37d'); // admin boundary
    expect(darkColorFor('rgba(19, 19, 16, 1)')).toBe('#e8ddc4'); // city label ink
    expect(darkColorFor('rgba(241, 233, 218, 1)')).toBe('#2a2722'); // label halo
  });

  it('is case-insensitive for hex keys', () => {
    expect(darkColorFor('#EAEAEA')).toBe(darkColorFor('#eaeaea'));
  });

  it('falls back deterministically for unknown colors: light→charcoal, dark→cream', () => {
    const fromLight = darkColorFor('#fefefe');
    const fromDark = darkColorFor('#111111');
    expect(fromLight).toMatch(/^#[0-9a-f]{6}$/);
    expect(fromDark).toMatch(/^#[0-9a-f]{6}$/);
    expect(fromLight).not.toBe('#fefefe');
    expect(fromDark).not.toBe('#111111');
    // stable
    expect(darkColorFor('#fefefe')).toBe(fromLight);
  });

  it('returns unparseable values unchanged', () => {
    expect(darkColorFor('hsl(20 30% 40%)')).toBe('hsl(20 30% 40%)');
    expect(darkColorFor('currentColor')).toBe('currentColor');
  });
});

describe('buildBasemapPaintTable', () => {
  it('collects plain color paints with light=original, dark=transformed', () => {
    const table = buildBasemapPaintTable(
      styleWith([
        {
          id: 'water_areas',
          type: 'fill',
          paint: { 'fill-color': 'rgba(207, 179, 125, 1)', 'fill-opacity': 0.8 },
        },
      ]),
    );
    expect(table.water_areas['fill-color']).toEqual({
      light: 'rgba(207, 179, 125, 1)',
      dark: '#221f1b',
    });
    // non-color paints are not collected
    expect(table.water_areas['fill-opacity']).toBeUndefined();
  });

  it('rewrites color strings inside expressions, preserving structure', () => {
    const expr = [
      'interpolate',
      ['linear'],
      ['zoom'],
      10,
      'rgba(217, 217, 217, 1)',
      11,
      '#ffffff',
    ];
    const table = buildBasemapPaintTable(
      styleWith([{ id: 'roads_primary', type: 'line', paint: { 'line-color': expr } }]),
    );
    const dark = table.roads_primary['line-color'].dark as unknown[];
    expect(dark[0]).toBe('interpolate');
    expect(dark[3]).toBe(10);
    expect(dark[4]).toBe(darkColorFor('rgba(217, 217, 217, 1)'));
    expect(dark[6]).toBe(darkColorFor('#ffffff'));
    // original untouched (deep clone)
    expect(expr[4]).toBe('rgba(217, 217, 217, 1)');
  });

  it('maps pattern paints to dark:null so flat colors render in dark', () => {
    const table = buildBasemapPaintTable(
      styleWith([
        {
          id: 'background-pattern',
          type: 'background',
          paint: {
            'background-color': 'rgba(207, 179, 125, 1)',
            'background-pattern': 'woodblock-paper',
          },
        },
        {
          id: 'roads_residential',
          type: 'line',
          paint: { 'line-color': '#ffffff', 'line-pattern': 'woodblock-roadTest1c' },
        },
      ]),
    );
    expect(table['background-pattern']['background-pattern']).toEqual({
      light: 'woodblock-paper',
      dark: null,
    });
    expect(table.roads_residential['line-pattern']).toEqual({
      light: 'woodblock-roadTest1c',
      dark: null,
    });
  });

  it('adds icon-opacity dark:0 for symbol layers with an icon-image', () => {
    const table = buildBasemapPaintTable(
      styleWith([
        {
          id: 'city_labels_z6',
          type: 'symbol',
          layout: { 'icon-image': 'woodblock-3-tiered-house-small-2', 'text-field': ['get', 'name'] },
          paint: { 'text-color': 'rgba(19, 19, 16, 1)' },
        },
        {
          id: 'state_points_labels',
          type: 'symbol',
          layout: { 'text-field': ['get', 'name'] },
          paint: { 'text-color': 'rgba(146, 143, 129, 1)' },
        },
      ]),
    );
    expect(table.city_labels_z6['icon-opacity']).toEqual({ light: 1, dark: 0 });
    expect(table.state_points_labels['icon-opacity']).toBeUndefined();
    // text still recolored on the icon layer
    expect(table.city_labels_z6['text-color'].dark).toBe('#e8ddc4');
  });
});

describe('applyBasemapTheme', () => {
  it('sets each collected paint for the requested theme, skipping missing layers', () => {
    const table = buildBasemapPaintTable(
      styleWith([
        { id: 'land', type: 'fill', paint: { 'fill-color': 'rgba(236, 225, 203, 1)' } },
        { id: 'gone', type: 'fill', paint: { 'fill-color': '#ffffff' } },
      ]),
    );
    const setPaintProperty = vi.fn();
    const map = {
      getLayer: (id: string) => (id === 'land' ? { id } : undefined),
      setPaintProperty,
    };
    applyBasemapTheme(map, 'dark', table);
    expect(setPaintProperty).toHaveBeenCalledWith('land', 'fill-color', '#353028');
    expect(setPaintProperty).not.toHaveBeenCalledWith('gone', expect.anything(), expect.anything());
    setPaintProperty.mockClear();
    applyBasemapTheme(map, 'light', table);
    expect(setPaintProperty).toHaveBeenCalledWith('land', 'fill-color', 'rgba(236, 225, 203, 1)');
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `web/`:
```bash
pnpm exec vitest run src/lib/basemap-theme.test.ts
```
Expected: FAIL — cannot resolve `./basemap-theme`.

- [ ] **Step 3: Implement `web/src/lib/basemap-theme.ts`**

```ts
/**
 * Theme-aware recoloring of the OHM woodblock basemap.
 *
 * The woodblock style is a light "paper" design (tan background + sprite
 * patterns + ink lines). Dark mode recolors it to charcoal + cream ink at
 * runtime via setPaintProperty — the same mechanism the entity overlays use —
 * so a theme toggle never reloads the style or tiles.
 *
 * Two MapLibre quirks drive the shape of this module:
 *  - `*-pattern` paints OVERRIDE the corresponding color, and sprites can't be
 *    tinted → dark mode clears every pattern so the flat colors render.
 *  - sprite icons are ink drawings that disappear on dark → dark mode sets
 *    `icon-opacity: 0` (text labels on the same layer keep working).
 */
import type { StyleSpecification } from 'maplibre-gl';

export type BasemapPaintTable = Record<
  string,
  Record<string, { light: unknown; dark: unknown }>
>;

/** The subset of maplibregl.Map we mutate (kept narrow for tests). */
export interface MapLibreThemable {
  getLayer(id: string): unknown;
  setPaintProperty(layerId: string, name: string, value: unknown): void;
}

/**
 * Hand-picked dark counterparts for every color the woodblock style uses
 * (keys lowercased). Paper/water tones → charcoal steps; ink/grays → creams;
 * accents brightened. Colors OHM adds later fall through to fallbackDark().
 */
const WOODBLOCK_DARK_COLORS: Record<string, string> = {
  // paper / water (background, water_areas, canals, dams)
  'rgba(207, 179, 125, 1)': '#221f1b',
  // land fills
  'rgba(236, 225, 203, 1)': '#353028',
  // rivers (cream lines)
  'rgba(235, 222, 196, 1)': '#4a443b',
  // road fills (whites / near-whites) → muted warm
  '#ffffff': '#6f6555',
  'rgba(255, 255, 255, 1)': '#6f6555',
  '#eaeaea': '#6f6555',
  '#d5d5d5': '#6f6555',
  'rgba(217, 217, 217, 1)': '#6f6555',
  'rgba(204, 204, 204, 1)': '#6f6555',
  'rgba(210, 210, 210, 1)': '#6f6555',
  'rgba(255, 249, 241, 1)': '#6f6555',
  'rgba(251, 247, 245, 1)': '#5a5147',
  // road casings / rails / footways
  '#b3b3b3': '#4a443b',
  'rgba(179, 179, 179, 1)': '#4a443b',
  'rgba(215, 215, 215, 1)': '#4a443b',
  'rgba(197, 197, 197, 1)': '#4a443b',
  'rgba(210, 190, 190, 1)': '#554b41',
  'rgba(153, 153, 153, 1)': '#454039',
  // tunnels
  '#f5f5f5': '#3f3a32',
  // special roads
  'rgba(255, 207, 0, 1)': '#b3902e',
  // admin boundaries → light tan ink (the point of dark mode)
  'rgba(157, 169, 174, 1)': '#cfb37d',
  // labels: ink text → cream, halos → charcoal
  'rgba(19, 19, 16, 1)': '#e8ddc4',
  'rgba(146, 143, 129, 1)': '#b3a68e',
  'rgba(113, 110, 99, 1)': '#cfc2a8',
  'rgba(241, 233, 218, 1)': '#2a2722',
  // landuse label greens
  'rgba(122, 143, 61, 1)': '#9cae6f',
  'rgba(95, 107, 71, 1)': '#8a9a63',
  'rgba(228, 235, 209, 1)': '#242a17',
  'rgba(201, 213, 190, 1)': '#242a17',
  // buildings (gold) and outlines (red)
  'rgba(182, 143, 53, 1)': '#6e5a30',
  'rgba(170, 44, 44, 1)': '#d47a63',
};

/** Paint properties that carry colors. */
const COLOR_PROPS = new Set([
  'background-color',
  'fill-color',
  'fill-outline-color',
  'line-color',
  'text-color',
  'text-halo-color',
  'icon-color',
  'icon-halo-color',
]);

/** Paint properties that carry sprite patterns (cleared in dark). */
const PATTERN_PROPS = new Set(['background-pattern', 'fill-pattern', 'line-pattern']);

/** Parse #rgb/#rrggbb/rgb()/rgba() to [r,g,b] 0..255, or null. */
function parseColor(value: string): [number, number, number] | null {
  const hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(value.trim());
  if (hex) {
    let h = hex[1];
    if (h.length === 3) h = h.split('').map((c) => c + c).join('');
    const n = parseInt(h, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  const rgb = /^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i.exec(value.trim());
  if (rgb) return [Number(rgb[1]), Number(rgb[2]), Number(rgb[3])];
  return null;
}

/** Blend two [r,g,b] by t∈[0,1] and format as #rrggbb. */
function mix(a: [number, number, number], b: [number, number, number], t: number): string {
  const c = a.map((av, i) => Math.round(av + (b[i] - av) * t));
  return `#${c.map((v) => v.toString(16).padStart(2, '0')).join('')}`;
}

const CHARCOAL_LO: [number, number, number] = [0x22, 0x1f, 0x1b];
const CHARCOAL_HI: [number, number, number] = [0x4a, 0x44, 0x3b];
const CREAM_LO: [number, number, number] = [0xcf, 0xc2, 0xa8];
const CREAM_HI: [number, number, number] = [0xe8, 0xdd, 0xc4];

/**
 * Deterministic fallback for colors not in the lookup: light colors land in
 * the charcoal band, dark colors in the cream band (warm-hued either way).
 * Unparseable input is returned unchanged (never throws).
 */
function fallbackDark(value: string): string {
  const rgb = parseColor(value);
  if (!rgb) return value;
  const lum = (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255;
  return lum >= 0.5
    ? mix(CHARCOAL_LO, CHARCOAL_HI, 1 - lum)
    : mix(CREAM_LO, CREAM_HI, 1 - lum);
}

/** Dark counterpart for a single color string. */
export function darkColorFor(color: string): string {
  return WOODBLOCK_DARK_COLORS[color.toLowerCase()] ?? fallbackDark(color);
}

/** Deep-transform a paint value, replacing every color string inside. */
function darkenValue(value: unknown): unknown {
  if (typeof value === 'string') return darkColorFor(value);
  if (Array.isArray(value)) return value.map(darkenValue);
  return value;
}

type AnyLayer = {
  id: string;
  type: string;
  layout?: Record<string, unknown>;
  paint?: Record<string, unknown>;
};

/**
 * Build the per-layer light/dark paint table for a loaded basemap style.
 * `light` holds the style's original values; `dark` the transformed ones.
 */
export function buildBasemapPaintTable(style: StyleSpecification): BasemapPaintTable {
  const table: BasemapPaintTable = {};
  for (const layer of (style.layers ?? []) as AnyLayer[]) {
    const entry: Record<string, { light: unknown; dark: unknown }> = {};
    for (const [prop, value] of Object.entries(layer.paint ?? {})) {
      if (COLOR_PROPS.has(prop)) {
        entry[prop] = { light: value, dark: darkenValue(value) };
      } else if (PATTERN_PROPS.has(prop)) {
        entry[prop] = { light: value, dark: null };
      }
    }
    if (layer.type === 'symbol' && layer.layout?.['icon-image'] !== undefined) {
      entry['icon-opacity'] = {
        light: layer.paint?.['icon-opacity'] ?? 1,
        dark: 0,
      };
    }
    if (Object.keys(entry).length > 0) table[layer.id] = entry;
  }
  return table;
}

/** Flip every collected paint to the requested theme (missing layers skipped). */
export function applyBasemapTheme(
  map: MapLibreThemable,
  theme: 'light' | 'dark',
  table: BasemapPaintTable,
): void {
  for (const [layerId, props] of Object.entries(table)) {
    if (!map.getLayer(layerId)) continue;
    for (const [prop, values] of Object.entries(props)) {
      map.setPaintProperty(layerId, prop, values[theme]);
    }
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run from `web/`:
```bash
pnpm exec vitest run src/lib/basemap-theme.test.ts
```
Expected: PASS — all cases green.

- [ ] **Step 5: Full gates**

Run from `web/`:
```bash
pnpm lint && pnpm types:check && pnpm exec vitest run && pnpm build
```
Expected: all pass (48 existing + new tests; only the 2 pre-existing CommandPalette warnings).

- [ ] **Step 6: Commit**

```bash
git add web/src/lib/basemap-theme.ts web/src/lib/basemap-theme.test.ts
git commit -m "feat(web): basemap theme module — woodblock dark recoloring tables"
```

---

### Task 2: Wire the woodblock basemap into MapCanvas

**Files:**
- Modify: `web/src/lib/map-config.ts` (the `OHM_STYLE_URL` constant, near the top)
- Modify: `web/src/components/map/MapCanvas.tsx`
- Modify: `web/src/styles.css` (remove the dark map filter rule at the end)

**Interfaces:**
- Consumes (from Task 1, exact signatures):
  - `buildBasemapPaintTable(style: StyleSpecification): BasemapPaintTable`
  - `applyBasemapTheme(map, theme: 'light' | 'dark', table): void`
  - `type BasemapPaintTable`
- Consumes (existing): `useTheme` from `@/lib/theme` (already subscribed in MapCanvas as `const theme = useTheme((s) => s.theme);`); `loadHistoricalBasemapStyle(): Promise<StyleSpecification>`.
- Produces: nothing further; this is the leaf task.

- [ ] **Step 1: Switch the basemap URL**

In `web/src/lib/map-config.ts`, change:
```ts
export const OHM_STYLE_URL =
    'https://www.openhistoricalmap.org/map-styles/main/main.json';
```
to:
```ts
export const OHM_STYLE_URL =
    'https://www.openhistoricalmap.org/map-styles/woodblock/woodblock.json';
```
Leave `HISTORICAL_BASEMAP_FALLBACK_STYLE_URL`, attribution, and all normalization functions untouched.

- [ ] **Step 2: Build the paint table at style load in MapCanvas**

In `web/src/components/map/MapCanvas.tsx`:

(a) Add the import next to the other `@/lib` imports:
```tsx
import {
  applyBasemapTheme,
  buildBasemapPaintTable,
  type BasemapPaintTable,
} from '@/lib/basemap-theme';
```

(b) Add a ref alongside the other refs in the component (near `const mapRef = ...`):
```tsx
  const basemapTableRef = useRef<BasemapPaintTable | null>(null);
```

(c) In the init effect, inside `loadHistoricalBasemapStyle().then((style) => { ... })`, immediately after the `if (cancelled) return;` line, add:
```tsx
      basemapTableRef.current = buildBasemapPaintTable(style);
```

- [ ] **Step 3: Apply dark basemap on boot-in-dark**

Still in `MapCanvas.tsx`, inside the `map.on('load', async () => { ... })` handler: right after `await registerGroupMarkers(map);` and its `if (cancelled) return;` guard, add:
```tsx
        // The style itself is light; if the app booted dark, recolor the
        // basemap before first meaningful paint of the overlays.
        if (
          document.documentElement.classList.contains('dark') &&
          basemapTableRef.current
        ) {
          applyBasemapTheme(map, 'dark', basemapTableRef.current);
        }
```

- [ ] **Step 4: Apply basemap theme in the existing theme effect**

In the theme-reactive effect (`useEffect(..., [theme])` near the bottom of `MapCanvas.tsx`), after the `if (!map) return;` guard and before the entity-layer recoloring, add:
```tsx
    if (basemapTableRef.current) {
      applyBasemapTheme(map, theme, basemapTableRef.current);
    }
```

- [ ] **Step 5: Remove the CSS dim filter**

In `web/src/styles.css`, delete this entire rule (including its comment) at the end of the file:
```css
/* In dark mode the external OHM basemap stays light — dim it into the charcoal
   chrome. Targets only the WebGL canvas, so DOM controls stay crisp. */
.dark .maplibregl-canvas {
  filter: brightness(0.82) contrast(1.05) sepia(0.08);
}
```

- [ ] **Step 6: Full gates**

Run from `web/`:
```bash
pnpm lint && pnpm types:check && pnpm exec vitest run && pnpm build
```
Expected: all pass.

- [ ] **Step 7: Visual check (controller does this — implementer skips)**

Both themes at `:5173`: light shows the woodblock paper map (texture, ink roads, tan water); dark shows charcoal map body, tan `#cfb37d` country boundaries, cream labels, no paper texture, no sprite icons; toggling is instant (no tile reload); timeline year scrub still filters the basemap; entity overlays/markers unchanged.

- [ ] **Step 8: Commit**

```bash
git add web/src/lib/map-config.ts web/src/components/map/MapCanvas.tsx web/src/styles.css
git commit -m "feat(web): woodblock basemap with runtime dark recoloring"
```

---

## Self-Review Notes

- **Spec coverage:** §1 style switch → Task 2 step 1. §2 module (lookup, fallback, table builder incl. expressions + patterns + icon-opacity, applier) → Task 1. §3 MapCanvas integration (load-time table, boot-in-dark, theme effect) → Task 2 steps 2–4. §4 CSS cleanup → Task 2 step 5. Testing section → Task 1 tests + gates + controller visual. Fallback-style caveat needs no code (the table builder + fallbackDark handle any style generically).
- **Type consistency:** `BasemapPaintTable`, `buildBasemapPaintTable`, `applyBasemapTheme`, `darkColorFor` named identically in both tasks; `MapLibreThemable` is structural so the fake map in tests and the real `maplibregl.Map` both satisfy it.
- **Spec deviation (deliberate):** the spec's `darkenFallback` name became `fallbackDark` (private) + exported `darkColorFor`; spec's "hide icon-only symbol layers via visibility" was refined to `icon-opacity: 0` for ALL icon-bearing symbol layers after discovering city labels carry icon+text in one layer (visibility would have killed the labels). The spec file's §2 text is superseded by this plan on those two details.
