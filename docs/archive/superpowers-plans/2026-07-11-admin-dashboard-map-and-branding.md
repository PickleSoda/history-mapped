# Admin Dashboard Map Remake + Branding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the admin dashboard the web Atlas's entity map rendering (group glyph markers, name labels, group-colored territories, viewport loading) and replace Laravel-starter branding with History Mapped.

**Architecture:** A new self-contained `DashboardMap` component in the admin bundle ports the web's proven pieces: an `entity-map-icons` lib (per-group SVG disc markers), the three-layer entity rendering from the web's `MapCanvas` (fill/line/symbol), and a TanStack Query bbox+year fetch against the same `/api/v1/entities/map` endpoint the SPA uses. The shared `HistoricalMapViewer` is untouched. Branding is a mechanical text/link sweep plus a minimal rewrite of the `/` landing page.

**Tech Stack:** React 19 + TypeScript (Inertia admin bundle in `api/resources/js`), MapLibre GL 5, TanStack Query (already used on the dashboard), Vitest + jsdom (existing config at `api/vitest.config.ts`).

## Global Constraints

- All work under `api/resources/js` (+ nothing outside `api/`). Do NOT touch `web/`.
- Do NOT modify `historical-map-viewer.tsx`, `map-editor.tsx`, the entity edit page, or `entity-history-panel.tsx`.
- Group palette (exact, from the spec): polity `#b4543f`, place `#6b7f4a`, event `#bd8a2c`, economy `#4d6a86`, culture `#8a5673`, default `#71717a`.
- Map endpoint + params exactly: `GET /api/v1/entities/map?bbox_min_lng=…&bbox_min_lat=…&bbox_max_lng=…&bbox_max_lat=…&zoom_level=…&min_results=24&limit=2000&year=…` (session-cookie fetch with `Accept: application/json`, like the dashboard's existing queries).
- Branding strings/links exactly: logo text `History Mapped`; Repository → `https://github.com/PickleSoda/history-mapped`; Documentation → `https://github.com/PickleSoda/history-mapped/tree/develop/docs`; welcome tagline `An interactive historical atlas`.
- **All admin commands run inside the `app` container:** `docker compose -f docker/docker-compose.yml exec app <cmd>` from the repo root. Before running tests after editing files, restart the container once (`docker compose -f docker/docker-compose.yml restart app`) — Docker Desktop stale-bind-mount gotcha. (Host `api/node_modules` is a container volume; host-side npm will not work.)
- Gates after each task: `exec app npm run lint:check`, `exec app npm run types:check`, `exec app npx vitest run` — all green. (`lint` autofixes; use `lint:check` to verify.)

---

## File Structure

| File | Responsibility |
|---|---|
| `api/resources/js/lib/entity-map-icons.ts` | **new** — group palette constants, maplibre group-color match expression, SVG glyph marker generation + idempotent registration |
| `api/resources/js/lib/__tests__/entity-map-icons.test.ts` | **new** — unit tests for the lib |
| `api/resources/js/components/dashboard-map.tsx` | **new** — self-contained viewport-driven entity map |
| `api/resources/js/components/__tests__/dashboard-map.test.tsx` | **new** — render test with mocked maplibre |
| `api/resources/js/pages/dashboard.tsx` | swap viewer for `DashboardMap`; drop year-bulk query |
| `api/resources/js/components/app-logo.tsx` | logo text |
| `api/resources/js/components/app-sidebar.tsx` | footer links |
| `api/resources/js/components/app-header.tsx` | same links |
| `api/resources/js/pages/welcome.tsx` | minimal History Mapped landing |

---

### Task 1: `entity-map-icons` lib (TDD)

**Files:**
- Create: `api/resources/js/lib/entity-map-icons.ts`
- Test: `api/resources/js/lib/__tests__/entity-map-icons.test.ts`

**Interfaces:**
- Consumes: nothing (pure lib; only a structural map type).
- Produces (Task 2 relies on these exact names):
  - `GROUP_COLORS: Record<string, string>` — UPPERCASE group → hex (incl. `DEFAULT`)
  - `groupColorExpression(): maplibregl.ExpressionSpecification` — `match` on `entity_group`
  - `markerImageId(group: string): string` — `marker-<UPPERCASE>`
  - `registerGroupMarkers(map: MarkerHost): Promise<void>` where `MarkerHost = { hasImage(id: string): boolean; addImage(id: string, img: HTMLImageElement, opts?: { pixelRatio?: number }): void }`

- [ ] **Step 1: Write the failing test**

Create `api/resources/js/lib/__tests__/entity-map-icons.test.ts`:

```ts
// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import {
    GROUP_COLORS,
    groupColorExpression,
    markerImageId,
    registerGroupMarkers,
} from '../entity-map-icons';

describe('GROUP_COLORS', () => {
    it('carries the five group accents plus a default', () => {
        expect(GROUP_COLORS).toEqual({
            POLITY: '#b4543f',
            PLACE: '#6b7f4a',
            EVENT: '#bd8a2c',
            ECONOMY: '#4d6a86',
            CULTURE: '#8a5673',
            DEFAULT: '#71717a',
        });
    });
});

describe('groupColorExpression', () => {
    it('builds a match on entity_group ending in the default color', () => {
        const expr = groupColorExpression() as unknown[];
        expect(expr[0]).toBe('match');
        expect(expr[1]).toEqual(['get', 'entity_group']);
        expect(expr).toContain('POLITY');
        expect(expr).toContain('#b4543f');
        expect(expr[expr.length - 1]).toBe('#71717a');
    });
});

describe('markerImageId', () => {
    it('uppercases the group into the image id', () => {
        expect(markerImageId('polity')).toBe('marker-POLITY');
        expect(markerImageId('CULTURE')).toBe('marker-CULTURE');
    });
});

describe('registerGroupMarkers', () => {
    it('registers one image per group plus the default, skipping existing', async () => {
        const existing = new Set<string>(['marker-POLITY']);
        const addImage = vi.fn((id: string) => existing.add(id));
        const map = {
            hasImage: (id: string) => existing.has(id),
            addImage,
        };

        // jsdom never fires Image.onload — resolve loads synchronously instead.
        const originalImage = globalThis.Image;
        class InstantImage {
            public onload: (() => void) | null = null;
            public onerror: (() => void) | null = null;
            public set src(_v: string) {
                queueMicrotask(() => this.onload?.());
            }
        }
        vi.stubGlobal('Image', InstantImage);

        try {
            await registerGroupMarkers(map);
        } finally {
            vi.stubGlobal('Image', originalImage);
        }

        const added = addImage.mock.calls.map((c) => c[0]).sort();
        expect(added).toEqual([
            'marker-CULTURE',
            'marker-DEFAULT',
            'marker-ECONOMY',
            'marker-EVENT',
            'marker-PLACE',
        ]);
    });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run from the repo root:
```bash
docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/lib/__tests__/entity-map-icons.test.ts
```
Expected: FAIL — cannot resolve `../entity-map-icons`.

- [ ] **Step 3: Implement `api/resources/js/lib/entity-map-icons.ts`**

```ts
/**
 * Per-group entity map markers for the admin dashboard — a port of the public
 * SPA's marker lib (web/src/lib/map-icons.ts). The admin bundle has no --g-*
 * CSS variables, so the group palette lives here as constants.
 */
import type maplibregl from 'maplibre-gl';

/** UPPERCASE entity group → accent hex (web light palette). */
export const GROUP_COLORS: Record<string, string> = {
    POLITY: '#b4543f',
    PLACE: '#6b7f4a',
    EVENT: '#bd8a2c',
    ECONOMY: '#4d6a86',
    CULTURE: '#8a5673',
    DEFAULT: '#71717a',
};

/** maplibre match expression: feature entity_group → accent color. */
export function groupColorExpression(): maplibregl.ExpressionSpecification {
    return [
        'match',
        ['get', 'entity_group'],
        'POLITY',
        GROUP_COLORS.POLITY,
        'PLACE',
        GROUP_COLORS.PLACE,
        'EVENT',
        GROUP_COLORS.EVENT,
        'ECONOMY',
        GROUP_COLORS.ECONOMY,
        'CULTURE',
        GROUP_COLORS.CULTURE,
        GROUP_COLORS.DEFAULT,
    ];
}

/** lucide 24×24 glyph bodies (stroke-drawn), keyed by UPPERCASE entity group. */
const GROUP_GLYPHS: Record<string, string> = {
    // crown
    POLITY: '<path d="M11.562 3.266a.5.5 0 0 1 .876 0L15.39 8.87a1 1 0 0 0 1.516.294L21.183 5.5a.5.5 0 0 1 .798.519l-2.834 10.246a1 1 0 0 1-.956.734H5.81a1 1 0 0 1-.957-.734L2.02 6.02a.5.5 0 0 1 .798-.519l4.276 3.664a1 1 0 0 0 1.516-.294z"/><path d="M5 21h14"/>',
    // map-pin
    PLACE: '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
    // star
    EVENT: '<path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.79 21.61a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.554 10.4a.53.53 0 0 1 .294-.904l5.166-.756a2.122 2.122 0 0 0 1.597-1.16z"/>',
    // coins
    ECONOMY: '<circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="m16.71 13.88.7.71-2.82 2.82"/>',
    // landmark
    CULTURE: '<path d="M10 18v-7"/><path d="M11.12 2.198a2 2 0 0 1 1.76.006l7.866 3.847c.476.233.31.949-.22.949H3.474c-.53 0-.695-.716-.22-.949z"/><path d="M14 18v-7"/><path d="M18 18v-7"/><path d="M3 22h18"/><path d="M6 18v-7"/>',
};

/** Plain dot fallback for any group without a dedicated glyph. */
const DEFAULT_GLYPH = '<circle cx="12" cy="12" r="4"/>';

function markerSvg(color: string, glyph: string): string {
    return [
        '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">',
        `<circle cx="24" cy="24" r="19" fill="${color}" stroke="#ffffff" stroke-width="3"/>`,
        '<g transform="translate(14.4 14.4) scale(0.8)" fill="none" stroke="#ffffff"',
        ' stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">',
        glyph,
        '</g></svg>',
    ].join('');
}

function loadImage(svg: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
        const img = new Image(48, 48);
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
    });
}

/** The icon-image id a feature's group maps to (mirror in the symbol layout). */
export function markerImageId(group: string): string {
    return `marker-${group.toUpperCase()}`;
}

/** The subset of maplibregl.Map we need (kept structural for tests). */
export type MarkerHost = {
    hasImage(id: string): boolean;
    addImage(
        id: string,
        img: HTMLImageElement,
        opts?: { pixelRatio?: number },
    ): void;
};

/**
 * Register a marker image per group (+ a default). Idempotent — skips images
 * that already exist, so it is safe to call after a style reload.
 */
export async function registerGroupMarkers(map: MarkerHost): Promise<void> {
    const groups = [
        ...Object.keys(GROUP_GLYPHS).map((g) => ({
            id: markerImageId(g),
            color: GROUP_COLORS[g] ?? GROUP_COLORS.DEFAULT,
            glyph: GROUP_GLYPHS[g],
        })),
        { id: 'marker-DEFAULT', color: GROUP_COLORS.DEFAULT, glyph: DEFAULT_GLYPH },
    ];

    await Promise.all(
        groups.map(async ({ id, color, glyph }) => {
            if (map.hasImage(id)) return;
            const img = await loadImage(markerSvg(color, glyph));
            if (!map.hasImage(id)) map.addImage(id, img, { pixelRatio: 2 });
        }),
    );
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
docker compose -f docker/docker-compose.yml restart app
docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/lib/__tests__/entity-map-icons.test.ts
```
Expected: PASS (4 tests).

- [ ] **Step 5: Full gates**

```bash
docker compose -f docker/docker-compose.yml exec app npm run lint:check
docker compose -f docker/docker-compose.yml exec app npm run types:check
docker compose -f docker/docker-compose.yml exec app npx vitest run
```
Expected: all green (existing suite + 4 new).

- [ ] **Step 6: Commit**

```bash
git add api/resources/js/lib/entity-map-icons.ts api/resources/js/lib/__tests__/entity-map-icons.test.ts
git commit -m "feat(admin): entity map marker lib (port of web map-icons)"
```

---

### Task 2: `DashboardMap` component + dashboard wiring

**Files:**
- Create: `api/resources/js/components/dashboard-map.tsx`
- Test: `api/resources/js/components/__tests__/dashboard-map.test.tsx`
- Modify: `api/resources/js/pages/dashboard.tsx`

**Interfaces:**
- Consumes (Task 1, exact): `groupColorExpression()`, `markerImageId` (indirectly via icon-image concat), `registerGroupMarkers(map)`; admin existing: `loadHistoricalBasemapStyle()` from `@/lib/map-config`, `applyOhmLayerDateFilter(map, date)` from `@/lib/ohm-layer-date-filter`.
- Produces: `DashboardMap` React component with props `{ year: number; onSelect: (id: string | null) => void; onCountChange?: (n: number) => void; className?: string }`.

- [ ] **Step 1: Write the failing render test**

Create `api/resources/js/components/__tests__/dashboard-map.test.tsx`:

```tsx
// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import DashboardMap from '../dashboard-map';

const mapState = vi.hoisted(() => ({
    instance: null as null | {
        sources: Map<string, { setData: ReturnType<typeof vi.fn> }>;
        layers: string[];
        emit: (event: string) => void;
    },
}));

vi.mock('maplibre-gl', () => ({
    default: {
        Map: class MockMap {
            public sources = new Map<string, { setData: ReturnType<typeof vi.fn> }>();
            public layers: string[] = [];
            private handlers = new Map<string, Set<() => void>>();
            public constructor() {
                mapState.instance = this as never;
                queueMicrotask(() => this.emit('load'));
            }
            public on(event: string, a: unknown, b?: unknown) {
                const handler = (typeof a === 'function' ? a : b) as () => void;
                if (!this.handlers.has(event)) this.handlers.set(event, new Set());
                this.handlers.get(event)!.add(handler);
                return this;
            }
            public emit(event: string) {
                this.handlers.get(event)?.forEach((h) => h());
            }
            public addSource(id: string) {
                this.sources.set(id, { setData: vi.fn() });
            }
            public getSource(id: string) {
                return this.sources.get(id);
            }
            public addLayer(spec: { id: string }) {
                this.layers.push(spec.id);
            }
            public getLayer(id: string) {
                return this.layers.includes(id) ? { id } : undefined;
            }
            public getBounds() {
                return {
                    getWest: () => -10,
                    getSouth: () => 30,
                    getEast: () => 30,
                    getNorth: () => 60,
                };
            }
            public getZoom() {
                return 4;
            }
            public getCanvas() {
                return { style: { cursor: '' } };
            }
            public queryRenderedFeatures() {
                return [];
            }
            public setFilter() {}
            public getFilter() {
                return null;
            }
            public getStyle() {
                return { layers: [] };
            }
            public hasImage() {
                return true;
            }
            public addImage() {}
            public remove() {}
        },
        LngLatBounds: class {},
    },
}));

vi.mock('@/lib/map-config', () => ({
    loadHistoricalBasemapStyle: vi.fn(async () => ({ version: 8, sources: {}, layers: [] })),
    OHM_ATTRIBUTION: 'ohm',
}));

const fetchMock = vi.fn(async () => ({
    ok: true,
    json: async () => ({ type: 'FeatureCollection', features: [] }),
}));
vi.stubGlobal('fetch', fetchMock);

function renderMap() {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={qc}>
            <DashboardMap year={1121} onSelect={() => {}} />
        </QueryClientProvider>,
    );
}

afterEach(() => {
    fetchMock.mockClear();
    mapState.instance = null;
});

describe('DashboardMap', () => {
    it('adds the entities source and the three entity layers on load', async () => {
        renderMap();
        await waitFor(() => {
            expect(mapState.instance).not.toBeNull();
            expect(mapState.instance!.sources.has('entities')).toBe(true);
        });
        expect(mapState.instance!.layers).toEqual(
            expect.arrayContaining(['entities-fill', 'entities-line', 'entities-symbols']),
        );
    });

    it('queries the viewport map endpoint with bbox, zoom and year', async () => {
        renderMap();
        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalled();
        });
        const url = String(fetchMock.mock.calls[0][0]);
        expect(url).toContain('/api/v1/entities/map?');
        expect(url).toContain('bbox_min_lng=-10');
        expect(url).toContain('bbox_max_lat=60');
        expect(url).toContain('zoom_level=4');
        expect(url).toContain('year=1121');
        expect(url).toContain('min_results=24');
        expect(url).toContain('limit=2000');
    });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/components/__tests__/dashboard-map.test.tsx
```
Expected: FAIL — cannot resolve `../dashboard-map`.

- [ ] **Step 3: Implement `api/resources/js/components/dashboard-map.tsx`**

```tsx
/**
 * Dashboard entity map — the admin counterpart of the public SPA's MapCanvas.
 * Viewport-driven: re-queries /api/v1/entities/map for the visible bbox + year
 * and renders group-colored territories, glyph markers and name labels.
 */
import { useQuery } from '@tanstack/react-query';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useRef, useState } from 'react';
import {
    groupColorExpression,
    registerGroupMarkers,
} from '@/lib/entity-map-icons';
import { loadHistoricalBasemapStyle } from '@/lib/map-config';
import { applyOhmLayerDateFilter } from '@/lib/ohm-layer-date-filter';

const SOURCE_ID = 'entities';
const FILL_LAYER = 'entities-fill';
const LINE_LAYER = 'entities-line';
const SYMBOL_LAYER = 'entities-symbols';
const MOVE_DEBOUNCE_MS = 250;
const EMPTY_FC = { type: 'FeatureCollection', features: [] } as const;

type Bbox = { w: number; s: number; e: number; n: number };

type FeatureCollectionLike = {
    type: 'FeatureCollection';
    features: Array<{ properties?: { id?: string } }>;
};

type Props = {
    year: number;
    onSelect: (id: string | null) => void;
    onCountChange?: (n: number) => void;
    className?: string;
};

export default function DashboardMap({
    year,
    onSelect,
    onCountChange,
    className,
}: Props) {
    const containerRef = useRef<HTMLDivElement>(null);
    const mapRef = useRef<maplibregl.Map | null>(null);
    const [bbox, setBbox] = useState<Bbox | null>(null);
    const [zoom, setZoom] = useState(2);
    const [mapReady, setMapReady] = useState(false);

    const onSelectRef = useRef(onSelect);
    onSelectRef.current = onSelect;
    const yearRef = useRef(year);
    yearRef.current = year;

    // ── init map once ─────────────────────────────────────────────────────────
    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        let cancelled = false;
        let mapInstance: maplibregl.Map | null = null;
        let timer: ReturnType<typeof setTimeout>;

        void loadHistoricalBasemapStyle().then((style) => {
            if (cancelled) return;

            const map = new maplibregl.Map({
                container,
                style,
                center: [15, 45],
                zoom: 3.2,
                attributionControl: { compact: true },
            });
            mapInstance = map;
            mapRef.current = map;

            map.on('load', () => {
                void registerGroupMarkers(map).then(() => {
                    if (cancelled) return;

                    map.addSource(SOURCE_ID, {
                        type: 'geojson',
                        data: EMPTY_FC as never,
                    });

                    const groupColor = groupColorExpression();
                    map.addLayer({
                        id: FILL_LAYER,
                        type: 'fill',
                        source: SOURCE_ID,
                        filter: ['match', ['geometry-type'], ['Polygon', 'MultiPolygon'], true, false],
                        paint: { 'fill-color': groupColor, 'fill-opacity': 0.15 },
                    });
                    map.addLayer({
                        id: LINE_LAYER,
                        type: 'line',
                        source: SOURCE_ID,
                        filter: ['match', ['geometry-type'], ['Polygon', 'MultiPolygon'], true, false],
                        paint: { 'line-color': groupColor, 'line-width': 1 },
                    });
                    map.addLayer({
                        id: SYMBOL_LAYER,
                        type: 'symbol',
                        source: SOURCE_ID,
                        filter: ['match', ['geometry-type'], ['Point', 'MultiPoint'], true, false],
                        layout: {
                            'icon-image': [
                                'coalesce',
                                ['image', ['concat', 'marker-', ['get', 'entity_group']]],
                                ['image', 'marker-DEFAULT'],
                            ],
                            'icon-size': 0.8,
                            'icon-allow-overlap': true,
                            'icon-anchor': 'bottom',
                            'text-field': ['get', 'name'],
                            'text-size': 11,
                            'text-offset': [0, 0.4],
                            'text-anchor': 'top',
                            'text-optional': true,
                            'text-max-width': 8,
                        },
                        paint: {
                            'text-color': '#2a2722',
                            'text-halo-color': '#ffffff',
                            'text-halo-width': 1.4,
                        },
                    });

                    for (const layerId of [SYMBOL_LAYER, FILL_LAYER]) {
                        map.on('mouseenter', layerId, () => {
                            map.getCanvas().style.cursor = 'pointer';
                        });
                        map.on('mouseleave', layerId, () => {
                            map.getCanvas().style.cursor = '';
                        });
                    }

                    map.on('click', (e) => {
                        const layers = [SYMBOL_LAYER, FILL_LAYER].filter((l) =>
                            map.getLayer(l),
                        );
                        const hit = layers.length
                            ? map.queryRenderedFeatures(e.point, { layers })[0]
                            : undefined;
                        const id = hit?.properties?.id;
                        onSelectRef.current(
                            typeof id === 'string' && id ? id : null,
                        );
                    });

                    applyOhmLayerDateFilter(map, String(yearRef.current));

                    const publishViewport = () => {
                        const b = map.getBounds();
                        setBbox({
                            w: b.getWest(),
                            s: b.getSouth(),
                            e: b.getEast(),
                            n: b.getNorth(),
                        });
                        setZoom(Math.round(map.getZoom()));
                    };
                    publishViewport();
                    map.on('moveend', () => {
                        clearTimeout(timer);
                        timer = setTimeout(publishViewport, MOVE_DEBOUNCE_MS);
                    });

                    setMapReady(true);
                });
            });
        });

        return () => {
            cancelled = true;
            clearTimeout(timer);
            mapInstance?.remove();
            mapRef.current = null;
        };
        // Mount once; year/bbox sync happens in the effects below.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // ── re-filter the OHM basemap when the year changes ───────────────────────
    useEffect(() => {
        const map = mapRef.current;
        if (!map || !mapReady) return;
        applyOhmLayerDateFilter(map, String(year));
    }, [year, mapReady]);

    // ── viewport query (same endpoint + params as the public SPA) ─────────────
    const entitiesQuery = useQuery({
        queryKey: ['dashboard-map-viewport', bbox, zoom, year],
        enabled: bbox !== null,
        placeholderData: (prev) => prev,
        queryFn: async () => {
            const params = new URLSearchParams({
                bbox_min_lng: String(bbox!.w),
                bbox_min_lat: String(bbox!.s),
                bbox_max_lng: String(bbox!.e),
                bbox_max_lat: String(bbox!.n),
                zoom_level: String(zoom),
                min_results: '24',
                limit: '2000',
                year: String(year),
            });
            const response = await fetch(
                `/api/v1/entities/map?${params.toString()}`,
                { headers: { Accept: 'application/json' } },
            );
            if (!response.ok) {
                throw new Error(`Failed to load map entities (${response.status})`);
            }
            return (await response.json()) as FeatureCollectionLike;
        },
    });

    // ── push data + publish count ──────────────────────────────────────────────
    const data = entitiesQuery.data;
    useEffect(() => {
        const map = mapRef.current;
        if (!map || !mapReady || !data) return;
        const source = map.getSource(SOURCE_ID) as
            | maplibregl.GeoJSONSource
            | undefined;
        source?.setData(data as never);
        onCountChange?.(data.features.length);
        // onCountChange is a stable-enough page callback; keyed on data only.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [data, mapReady]);

    return <div ref={containerRef} className={className} />;
}
```

- [ ] **Step 4: Run the component test to verify it passes**

```bash
docker compose -f docker/docker-compose.yml restart app
docker compose -f docker/docker-compose.yml exec app npx vitest run resources/js/components/__tests__/dashboard-map.test.tsx
```
Expected: PASS (2 tests). If the mock's `emit('load')` fires before `registerGroupMarkers` resolves, the source appears one microtask later — the `waitFor` covers it.

- [ ] **Step 5: Wire the dashboard page**

In `api/resources/js/pages/dashboard.tsx`:

(a) Replace the viewer import:
```tsx
import DashboardMap from '@/components/dashboard-map';
```
(remove the `HistoricalMapViewer` import).

(b) Delete the `mapQuery` block (the `useQuery` whose `queryFn` fetches `/api/v1/entities/map/year?…`) and the `MapResponse`-related derivations (`mapFeatures`, `hasMapData`). Add a feature-count state next to the other state hooks:
```tsx
    const [featureCount, setFeatureCount] = useState(0);
```

(c) Replace the `<HistoricalMapViewer …/>` usage with:
```tsx
                            <DashboardMap
                                year={activeYear}
                                onSelect={(id) =>
                                    startTransition(() => setSelectedEntityId(id))
                                }
                                onCountChange={setFeatureCount}
                                className="h-full w-full"
                            />
```
Keep the surrounding container div and the side panel exactly as they are. The old `handleFeatureClick` helper becomes unused — delete it.

(d) Update the entity-count readout and the empty-state condition to use `featureCount` instead of `mapFeatures.length`/`hasMapData` (the readout text stays the same, e.g. `{featureCount} entities are currently visible.`). If the page renders a loading/error state off `mapQuery`, drop those branches — `DashboardMap` owns its loading now; keep the page's error text only if it referenced `selectedEntityQuery`.

(e) Remove now-unused types/imports (`MapResponse`, `GeoJsonLike` etc.) so `types:check`/lint stay clean.

- [ ] **Step 6: Full gates**

```bash
docker compose -f docker/docker-compose.yml exec app npm run lint:check
docker compose -f docker/docker-compose.yml exec app npm run types:check
docker compose -f docker/docker-compose.yml exec app npx vitest run
```
Expected: all green (existing suite + 6 new across both tasks).

- [ ] **Step 7: Visual check (controller does this — implementer skips)**

Admin at `:8000/dashboard`: glyph markers with group colors + name labels; territories tinted per group; pan/zoom re-fetches (count changes); year input re-filters basemap + entities; clicking a marker opens the side panel.

- [ ] **Step 8: Commit**

```bash
git add api/resources/js/components/dashboard-map.tsx api/resources/js/components/__tests__/dashboard-map.test.tsx api/resources/js/pages/dashboard.tsx
git commit -m "feat(admin): viewport-driven dashboard map with web-style entity rendering"
```

---

### Task 3: Branding sweep

**Files:**
- Modify: `api/resources/js/components/app-logo.tsx:11`
- Modify: `api/resources/js/components/app-sidebar.tsx:120-131`
- Modify: `api/resources/js/components/app-header.tsx:63-72`
- Modify: `api/resources/js/pages/welcome.tsx` (full content replacement)

**Interfaces:** none produced/consumed — mechanical sweep. (No unit tests; gates + visual.)

- [ ] **Step 1: Logo text**

In `api/resources/js/components/app-logo.tsx`, change the text node `Laravel Starter Kit` to `History Mapped` (leave markup/classes untouched).

- [ ] **Step 2: Sidebar + header links**

In `api/resources/js/components/app-sidebar.tsx`, replace the two `footerNavItems` hrefs:
```tsx
const footerNavItems: NavItem[] = [
    {
        title: 'Repository',
        href: 'https://github.com/PickleSoda/history-mapped',
        icon: FolderGit2,
    },
    {
        title: 'Documentation',
        href: 'https://github.com/PickleSoda/history-mapped/tree/develop/docs',
        icon: BookOpen,
    },
];
```
In `api/resources/js/components/app-header.tsx`, the same two items appear (around lines 63–72) — apply the same two `href` replacements there (titles/icons unchanged).

- [ ] **Step 3: Welcome page**

Replace the full contents of `api/resources/js/pages/welcome.tsx` with:

```tsx
import { Head, Link, usePage } from '@inertiajs/react';
import { dashboard, login, register } from '@/routes';

export default function Welcome({
    canRegister = true,
}: {
    canRegister?: boolean;
}) {
    const { auth } = usePage().props;

    return (
        <>
            <Head title="Welcome" />
            <div className="flex min-h-screen flex-col items-center bg-[#FDFDFC] p-6 text-[#1b1b18] lg:justify-center lg:p-8 dark:bg-[#0a0a0a]">
                <header className="mb-6 w-full max-w-4xl text-sm">
                    <nav className="flex items-center justify-end gap-4">
                        {auth.user ? (
                            <Link
                                href={dashboard()}
                                className="inline-block rounded-sm border border-[#19140035] px-5 py-1.5 text-sm leading-normal hover:border-[#1915014a] dark:border-[#3E3E3A] dark:text-[#EDEDEC] dark:hover:border-[#62605b]"
                            >
                                Dashboard
                            </Link>
                        ) : (
                            <>
                                <Link
                                    href={login()}
                                    className="inline-block rounded-sm border border-transparent px-5 py-1.5 text-sm leading-normal hover:border-[#19140035] dark:text-[#EDEDEC] dark:hover:border-[#3E3E3A]"
                                >
                                    Log in
                                </Link>
                                {canRegister && (
                                    <Link
                                        href={register()}
                                        className="inline-block rounded-sm border border-[#19140035] px-5 py-1.5 text-sm leading-normal hover:border-[#1915014a] dark:border-[#3E3E3A] dark:text-[#EDEDEC] dark:hover:border-[#62605b]"
                                    >
                                        Register
                                    </Link>
                                )}
                            </>
                        )}
                    </nav>
                </header>
                <div className="flex w-full items-center justify-center lg:grow">
                    <main className="flex w-full max-w-xl flex-col items-center gap-4 rounded-lg bg-white p-10 text-center shadow-[inset_0px_0px_0px_1px_rgba(26,26,0,0.16)] dark:bg-[#161615] dark:text-[#EDEDEC] dark:shadow-[inset_0px_0px_0px_1px_#fffaed2d]">
                        <h1 className="text-2xl font-semibold tracking-tight">
                            History Mapped
                        </h1>
                        <p className="text-[#706f6c] dark:text-[#A1A09A]">
                            An interactive historical atlas.
                        </p>
                        <div className="mt-2 flex gap-4 text-sm">
                            <a
                                href="https://github.com/PickleSoda/history-mapped"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="underline underline-offset-4 hover:text-[#1b1b18] dark:hover:text-white"
                            >
                                Repository
                            </a>
                            <a
                                href="https://github.com/PickleSoda/history-mapped/tree/develop/docs"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="underline underline-offset-4 hover:text-[#1b1b18] dark:hover:text-white"
                            >
                                Documentation
                            </a>
                        </div>
                    </main>
                </div>
            </div>
        </>
    );
}
```

- [ ] **Step 4: Full gates**

```bash
docker compose -f docker/docker-compose.yml exec app npm run lint:check
docker compose -f docker/docker-compose.yml exec app npm run types:check
docker compose -f docker/docker-compose.yml exec app npx vitest run
```
Expected: all green.

- [ ] **Step 5: Visual check (controller does this — implementer skips)**

`:8000/` shows the History Mapped landing (no Laravel content); sidebar logo says "History Mapped"; sidebar/header Repository + Documentation links point at the GitHub URLs.

- [ ] **Step 6: Commit**

```bash
git add api/resources/js/components/app-logo.tsx api/resources/js/components/app-sidebar.tsx api/resources/js/components/app-header.tsx api/resources/js/pages/welcome.tsx
git commit -m "feat(admin): History Mapped branding — landing page, logo, repo/docs links"
```

---

## Self-Review Notes

- **Spec coverage:** Part 1 decisions (dashboard-only → Task 2 touches only dashboard files; viewport+year → Task 2 query; side panel kept → `onSelect` wiring). Icon lib + palette → Task 1. Error handling (query error → component throws into TanStack error state; page copy per step 5d; layer guards + cancellation in component). Part 2 table → Task 3 one row per step. Operator `.env` note is spec-level (no task — uncommitted file).
- **Type consistency:** `groupColorExpression`/`registerGroupMarkers`/`markerImageId`/`GROUP_COLORS` identical between Task 1 exports, Task 1 tests, and Task 2 imports. `DashboardMap` props `{year, onSelect, onCountChange?, className?}` match Task 2 step 5c usage. `MarkerHost` structural type satisfies both the vitest fake and `maplibregl.Map`.
- **Placeholder scan:** none; every code step carries complete code; line anchors verified against the live files this session.
