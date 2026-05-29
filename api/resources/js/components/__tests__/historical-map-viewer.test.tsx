// @vitest-environment jsdom
import { act, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import HistoricalMapViewer from '../historical-map-viewer';

const mapTestState = vi.hoisted(() => ({
    latestMapInstance: null as {
        emitLayer: (event: string, layerId: string, payload?: any) => void;
        getSource: (sourceId: string) => { setData: ReturnType<typeof vi.fn> } | undefined;
    } | null,
}));

vi.mock('maplibre-gl', () => ({
    LngLatBounds: class LngLatBounds {},
    Map: class MockMap {
        public canvas = { style: { cursor: '' } };

        private sources = new Map<string, { setData: ReturnType<typeof vi.fn> }>();

        private layers = new Set<string>();

        private globalHandlers = new Map<string, Set<(event?: any) => void>>();

        private layerHandlers = new Map<string, Map<string, Set<(event?: any) => void>>>();

        public constructor() {
            mapTestState.latestMapInstance = this;

            queueMicrotask(() => {
                this.emit('load');
            });
        }

        public on(event: string, layerOrHandler: string | ((event?: any) => void), maybeHandler?: (event?: any) => void): void {
            if (typeof layerOrHandler === 'string' && maybeHandler) {
                const handlersByLayer = this.layerHandlers.get(event) ?? new Map<string, Set<(event?: any) => void>>();
                const handlers = handlersByLayer.get(layerOrHandler) ?? new Set<(event?: any) => void>();
                handlers.add(maybeHandler);
                handlersByLayer.set(layerOrHandler, handlers);
                this.layerHandlers.set(event, handlersByLayer);

                return;
            }

            if (typeof layerOrHandler === 'function') {
                const handlers = this.globalHandlers.get(event) ?? new Set<(event?: any) => void>();
                handlers.add(layerOrHandler);
                this.globalHandlers.set(event, handlers);
            }
        }

        public once(event: string, handler: (event?: any) => void): void {
            const onceHandler = (payload?: any) => {
                this.off(event, onceHandler);
                handler(payload);
            };

            this.on(event, onceHandler);
        }

        public off(event: string, layerOrHandler: string | ((event?: any) => void), maybeHandler?: (event?: any) => void): void {
            if (typeof layerOrHandler === 'string' && maybeHandler) {
                const handlersByLayer = this.layerHandlers.get(event);
                const handlers = handlersByLayer?.get(layerOrHandler);
                handlers?.delete(maybeHandler);

                return;
            }

            if (typeof layerOrHandler === 'function') {
                this.globalHandlers.get(event)?.delete(layerOrHandler);
            }
        }

        public emit(event: string, payload?: any): void {
            this.globalHandlers.get(event)?.forEach((handler) => handler(payload));
        }

        public emitLayer(event: string, layerId: string, payload?: any): void {
            this.layerHandlers.get(event)?.get(layerId)?.forEach((handler) => handler(payload));
        }

        public addSource(sourceId: string): void {
            this.sources.set(sourceId, { setData: vi.fn() });
        }

        public getSource(sourceId: string): { setData: ReturnType<typeof vi.fn> } | undefined {
            return this.sources.get(sourceId);
        }

        public addLayer(layer: { id: string }): void {
            this.layers.add(layer.id);
        }

        public getLayer(layerId: string): { id: string } | undefined {
            return this.layers.has(layerId) ? { id: layerId } : undefined;
        }

        public getStyle(): { layers: never[] } {
            return { layers: [] };
        }

        public project(): { x: number; y: number } {
            return { x: 120, y: 120 };
        }

        public getCanvas(): { style: { cursor: string } } {
            return this.canvas;
        }

        public setPaintProperty(): void {}

        public queryRenderedFeatures(): never[] {
            return [];
        }

        public fitBounds(): void {}

        public resize(): void {}

        public remove(): void {}
    },
}));

vi.mock('@/actions/App/Http/Api/V1/Controllers/MapResolutionController', () => ({
    resolveOhmFeature: vi.fn(),
}));

vi.mock('@/lib/map-config', () => ({
    loadHistoricalBasemapStyle: vi.fn(async () => ({
        version: 8,
        sources: {},
        layers: [],
    })),
}));

vi.mock('@/lib/ohm-layer-date-filter', () => ({
    applyOhmLayerDateFilter: vi.fn(),
}));

beforeAll(() => {
    class ResizeObserverMock {
        public observe(): void {}
        public disconnect(): void {}
    }

    vi.stubGlobal('ResizeObserver', ResizeObserverMock);
});

afterEach(() => {
    mapTestState.latestMapInstance = null;
});

describe('HistoricalMapViewer', () => {
    it('shows a popup when hovering a base point feature', async () => {
        const feature = {
            type: 'Feature',
            geometry: {
                type: 'Point',
                coordinates: [12.5, 41.9],
            },
            properties: {
                id: 'e1',
                name: 'Rome',
                entity_type: 'polity',
            },
        };

        render(
            <HistoricalMapViewer
                baseGeometries={[feature]}
                timeframeDate="100-01-01"
            />,
        );

        await waitFor(() => {
            expect(mapTestState.latestMapInstance?.getSource('base-geometry')).toBeDefined();
        });

        await act(async () => {
            mapTestState.latestMapInstance?.emitLayer('mouseenter', 'base-point', {
                features: [feature],
            });
        });

        expect(await screen.findByText('Rome')).toBeInTheDocument();
    });

    it('invokes the click callback when a base point feature is clicked', async () => {
        const onFeatureClick = vi.fn();
        const feature = {
            type: 'Feature',
            geometry: {
                type: 'Point',
                coordinates: [12.5, 41.9],
            },
            properties: {
                id: 'e1',
                name: 'Rome',
                entity_type: 'polity',
            },
        };

        render(
            <HistoricalMapViewer
                baseGeometries={[feature]}
                timeframeDate="100-01-01"
                onFeatureClick={onFeatureClick}
            />,
        );

        await waitFor(() => {
            expect(mapTestState.latestMapInstance?.getSource('base-geometry')).toBeDefined();
        });

        await act(async () => {
            mapTestState.latestMapInstance?.emitLayer('click', 'base-point', {
                features: [feature],
            });
        });

        expect(onFeatureClick).toHaveBeenCalledWith(feature);
    });
});