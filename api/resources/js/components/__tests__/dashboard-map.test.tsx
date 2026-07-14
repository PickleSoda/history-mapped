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
            public sources = new Map<
                string,
                { setData: ReturnType<typeof vi.fn> }
            >();
            public layers: string[] = [];
            private handlers = new Map<string, Set<() => void>>();
            public constructor() {
                mapState.instance = this as never;
                queueMicrotask(() => this.emit('load'));
            }
            public on(event: string, a: unknown, b?: unknown) {
                const handler = (typeof a === 'function' ? a : b) as () => void;

                if (!this.handlers.has(event)) {
                    this.handlers.set(event, new Set());
                }

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
    loadHistoricalBasemapStyle: vi.fn(async () => ({
        version: 8,
        sources: {},
        layers: [],
    })),
    OHM_ATTRIBUTION: 'ohm',
}));

const fetchMock = vi.fn(async (..._args: unknown[]) => ({
    ok: true,
    json: async () => ({ type: 'FeatureCollection', features: [] }),
}));
vi.stubGlobal('fetch', fetchMock);

function renderMap() {
    const qc = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    });

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
            expect.arrayContaining([
                'entities-fill',
                'entities-line',
                'entities-symbols',
            ]),
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
