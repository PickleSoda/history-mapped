/**
 * MapEditor — embedded map editor using MapLibre GL JS + Mapbox GL Draw.
 *
 * Renders a split-panel map for editing two geometry fields:
 *   - geojson:           Point or LineString (entity location/route)
 *   - territory_geojson: Polygon or MultiPolygon (entity territory/area)
 *
 * Base tiles: OpenFreeMap "liberty" style (free, no API key required).
 *
 * NOTE: @mapbox/mapbox-gl-draw types import from "mapbox-gl" but the library
 * works at runtime with maplibre-gl. We use `as unknown` casts where the type
 * mismatch would otherwise block compilation.
 */

import { useEffect, useRef, useState } from 'react';
import { Map } from 'maplibre-gl';
import { loadHistoricalBasemapStyle } from '@/lib/map-config';
import { normalizeToFeatureCollection } from '@/lib/geojson';
import 'maplibre-gl/dist/maplibre-gl.css';
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore — mapbox-gl-draw types reference mapbox-gl but the lib is maplibre-compatible
import MapboxDraw from '@mapbox/mapbox-gl-draw';
import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';
import { Button } from '@/components/ui/button';

// ── Types ────────────────────────────────────────────────────────────────────

type GeoJsonGeometry = Record<string, unknown> | null;

export type MapEditorProps = {
    /** Point/LineString geometry (geom column) */
    geojson: GeoJsonGeometry;
    /** Polygon/MultiPolygon geometry (territory_geom column) */
    territoryGeojson: GeoJsonGeometry;
    onChange: (geojson: GeoJsonGeometry, territoryGeojson: GeoJsonGeometry) => void;
};

type ActiveTab = 'location' | 'territory';

const DRAW_CONTROLS_LOCATION = {
    point: true,
    line_string: true,
    polygon: false,
    trash: true,
    combine_features: false,
    uncombine_features: false,
} as const;

const DRAW_CONTROLS_TERRITORY = {
    point: false,
    line_string: false,
    polygon: true,
    trash: true,
    combine_features: true,
    uncombine_features: true,
} as const;

/**
 * Patched draw styles for MapLibre GL JS v5 compatibility.
 *
 * @mapbox/mapbox-gl-draw default theme uses bare array literals inside a
 * `case` expression for `line-dasharray`, e.g.:
 *   ['case', ['==', ...], [0.2, 2], [2, 0]]
 *
 * MapLibre v5 requires these to be wrapped with `['literal', [...]]`:
 *   ['case', ['==', ...], ['literal', [0.2, 2]], ['literal', [2, 0]]]
 *
 * We also replace the single dashed-line layer with two solid layers
 * (active = dashed appearance via short segments, inactive = solid) to
 * avoid the expression entirely and keep things simple.
 */
const DRAW_STYLES = [
    // Polygon fill
    {
        id: 'gl-draw-polygon-fill',
        type: 'fill',
        filter: ['all', ['==', '$type', 'Polygon']],
        paint: {
            'fill-color': ['case', ['==', ['get', 'active'], 'true'], '#fbb03b', '#3bb2d0'],
            'fill-opacity': 0.1,
        },
    },
    // Lines — active (dashed via short width pulses: use opacity trick instead)
    {
        id: 'gl-draw-lines-active',
        type: 'line',
        filter: ['all', ['any', ['==', '$type', 'LineString'], ['==', '$type', 'Polygon']], ['==', ['get', 'active'], 'true']],
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
            'line-color': '#fbb03b',
            'line-dasharray': ['literal', [0.2, 2]],
            'line-width': 2,
        },
    },
    // Lines — inactive (solid)
    {
        id: 'gl-draw-lines-inactive',
        type: 'line',
        filter: ['all', ['any', ['==', '$type', 'LineString'], ['==', '$type', 'Polygon']], ['!=', ['get', 'active'], 'true']],
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
            'line-color': '#3bb2d0',
            'line-width': 2,
        },
    },
    // Point outer (white halo)
    {
        id: 'gl-draw-point-outer',
        type: 'circle',
        filter: ['all', ['==', '$type', 'Point'], ['==', 'meta', 'feature']],
        paint: {
            'circle-radius': ['case', ['==', ['get', 'active'], 'true'], 7, 5],
            'circle-color': '#fff',
        },
    },
    // Point inner (coloured)
    {
        id: 'gl-draw-point-inner',
        type: 'circle',
        filter: ['all', ['==', '$type', 'Point'], ['==', 'meta', 'feature']],
        paint: {
            'circle-radius': ['case', ['==', ['get', 'active'], 'true'], 5, 3],
            'circle-color': ['case', ['==', ['get', 'active'], 'true'], '#fbb03b', '#3bb2d0'],
        },
    },
    // Vertex outer
    {
        id: 'gl-draw-vertex-outer',
        type: 'circle',
        filter: ['all', ['==', '$type', 'Point'], ['==', 'meta', 'vertex'], ['!=', 'mode', 'simple_select']],
        paint: {
            'circle-radius': ['case', ['==', ['get', 'active'], 'true'], 7, 5],
            'circle-color': '#fff',
        },
    },
    // Vertex inner
    {
        id: 'gl-draw-vertex-inner',
        type: 'circle',
        filter: ['all', ['==', '$type', 'Point'], ['==', 'meta', 'vertex'], ['!=', 'mode', 'simple_select']],
        paint: {
            'circle-radius': ['case', ['==', ['get', 'active'], 'true'], 5, 3],
            'circle-color': '#fbb03b',
        },
    },
    // Midpoint
    {
        id: 'gl-draw-midpoint',
        type: 'circle',
        filter: ['all', ['==', 'meta', 'midpoint']],
        paint: { 'circle-radius': 3, 'circle-color': '#fbb03b' },
    },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function MapEditor({ geojson, territoryGeojson, onChange }: MapEditorProps) {
    const [activeTab, setActiveTab] = useState<ActiveTab>('location');

    // Refs to avoid stale closures in event handlers
    const geojsonRef = useRef<GeoJsonGeometry>(geojson);
    const territoryRef = useRef<GeoJsonGeometry>(territoryGeojson);
    const onChangeRef = useRef(onChange);

    useEffect(() => { geojsonRef.current = geojson; }, [geojson]);
    useEffect(() => { territoryRef.current = territoryGeojson; }, [territoryGeojson]);
    useEffect(() => { onChangeRef.current = onChange; }, [onChange]);

    return (
        <div className="rounded-lg border">
            {/* Tab bar */}
            <div className="flex border-b">
                <TabButton
                    active={activeTab === 'location'}
                    onClick={() => setActiveTab('location')}
                    label="Location / Route"
                    hint="Point or LineString"
                />
                <TabButton
                    active={activeTab === 'territory'}
                    onClick={() => setActiveTab('territory')}
                    label="Territory"
                    hint="Polygon / MultiPolygon"
                />
            </div>

            {/* Map panels — both rendered but only one visible, so map instances stay alive */}
            <MapPanel
                mapId="map-location"
                visible={activeTab === 'location'}
                initialGeometry={geojson}
                controls={DRAW_CONTROLS_LOCATION as unknown as MapboxDraw.MapboxDrawControls}
                onGeometryChange={(geometry) => {
                    onChangeRef.current(geometry, territoryRef.current);
                }}
            />
            <MapPanel
                mapId="map-territory"
                visible={activeTab === 'territory'}
                initialGeometry={territoryGeojson}
                controls={DRAW_CONTROLS_TERRITORY as unknown as MapboxDraw.MapboxDrawControls}
                onGeometryChange={(geometry) => {
                    onChangeRef.current(geojsonRef.current, geometry);
                }}
            />
        </div>
    );
}

// ── TabButton ─────────────────────────────────────────────────────────────────

function TabButton({
    active,
    onClick,
    label,
    hint,
}: {
    active: boolean;
    onClick: () => void;
    label: string;
    hint: string;
}) {
    return (
        <button
            type="button"
            onClick={onClick}
            className={[
                'flex flex-col px-4 py-2 text-sm font-medium transition-colors',
                active
                    ? 'border-b-2 border-primary text-primary'
                    : 'text-muted-foreground hover:text-foreground',
            ].join(' ')}
        >
            <span>{label}</span>
            <span className="text-muted-foreground text-xs font-normal">{hint}</span>
        </button>
    );
}

// ── MapPanel ──────────────────────────────────────────────────────────────────

type MapPanelProps = {
    mapId: string;
    visible: boolean;
    initialGeometry: GeoJsonGeometry;
    controls: MapboxDraw.MapboxDrawControls;
    onGeometryChange: (geometry: GeoJsonGeometry) => void;
};

function MapPanel({ mapId, visible, initialGeometry, controls, onGeometryChange }: MapPanelProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const mapRef = useRef<Map | null>(null);
    const drawRef = useRef<MapboxDraw | null>(null);
    const initialGeometryRef = useRef(initialGeometry);
    const onChangeRef = useRef(onGeometryChange);
    const applyingExternalGeometryRef = useRef(false);
    const lastAppliedGeometryJsonRef = useRef<string>('');

    useEffect(() => { onChangeRef.current = onGeometryChange; }, [onGeometryChange]);
    useEffect(() => { initialGeometryRef.current = initialGeometry; }, [initialGeometry]);

    const applyGeometryToDraw = (geometry: GeoJsonGeometry) => {
        const draw = drawRef.current;
        if (!draw) {
            return;
        }

        const featureCollection = normalizeToFeatureCollection([geometry]);
        const nextJson = JSON.stringify(featureCollection.features);
        if (nextJson === lastAppliedGeometryJsonRef.current) {
            return;
        }

        applyingExternalGeometryRef.current = true;
        draw.deleteAll();

        if (featureCollection.features.length > 0) {
            draw.set(featureCollection);
        }

        lastAppliedGeometryJsonRef.current = nextJson;
        applyingExternalGeometryRef.current = false;
    };

    // Initialise the map once on mount
    useEffect(() => {
        if (!containerRef.current || mapRef.current) {
            return;
        }

        let cancelled = false;

        loadHistoricalBasemapStyle()
            .then((style: Record<string, unknown>) => {
                if (cancelled || !containerRef.current) {
                    return;
                }

                const map = new Map({
                    container: containerRef.current,
                    style: style as Parameters<typeof Map.prototype.setStyle>[0],
                    center: [20, 30], // Default: roughly centred on the ancient world
                    zoom: 2,
                });

                const draw = new MapboxDraw({
                    displayControlsDefault: false,
                    controls,
                    styles: DRAW_STYLES as unknown as object[],
                });

                // MapboxDraw expects a mapbox-gl Map but works with maplibre-gl at runtime
                map.addControl(draw as unknown as Parameters<Map['addControl']>[0]);

                // @mapbox/mapbox-gl-draw renders its toolbar with class `mapboxgl-ctrl`
                // (the Mapbox prefix). MapLibre v5's CSS only grants `pointer-events: auto`
                // to `.maplibregl-ctrl`, so the toolbar buttons would be unclickable.
                // Fix: add the maplibre prefix class to every draw control group element.
                map.getContainer()
                    .querySelectorAll<HTMLElement>('.mapboxgl-ctrl-group')
                    .forEach((el) => el.classList.add('maplibregl-ctrl'));

                map.on('load', () => {
                    applyGeometryToDraw(initialGeometryRef.current);
                });

                // Emit changes on create/update/delete
                const emitChange = () => {
                    if (applyingExternalGeometryRef.current) {
                        return;
                    }

                    const fc = draw.getAll();
                    lastAppliedGeometryJsonRef.current = JSON.stringify(fc.features);
                    if (fc.features.length === 0) {
                        onChangeRef.current(null);
                        return;
                    }
                    if (fc.features.length === 1) {
                        // Emit the raw geometry object
                        onChangeRef.current(fc.features[0]!.geometry as unknown as GeoJsonGeometry);
                    } else {
                        // Multiple features — emit as FeatureCollection
                        onChangeRef.current(fc as unknown as GeoJsonGeometry);
                    }
                };

                map.on('draw.create', emitChange);
                map.on('draw.update', emitChange);
                map.on('draw.delete', emitChange);

                mapRef.current = map;
                drawRef.current = draw;
            })
            .catch(() => {
                // Style fetch failed — silently leave the map uninitialised
            });

        return () => {
            cancelled = true;
            mapRef.current?.remove();
            mapRef.current = null;
            drawRef.current = null;
        };
    // Run only once — controls are stable for the lifetime of the panel
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Resize the map when it becomes visible (the container was hidden on init)
    useEffect(() => {
        if (visible && mapRef.current) {
            setTimeout(() => mapRef.current?.resize(), 0);
        }
    }, [visible]);

    useEffect(() => {
        const draw = drawRef.current;
        const map = mapRef.current;
        if (!draw || !map || !map.isStyleLoaded()) {
            return;
        }

        applyGeometryToDraw(initialGeometry);
    }, [initialGeometry]);

    return (
        <div className={visible ? 'block' : 'hidden'}>
            <div ref={containerRef} style={{ height: '420px', width: '100%' }} />
            <div className="bg-muted/40 flex items-center justify-between border-t px-3 py-2 text-xs">
                <span className="text-muted-foreground">
                    Click the toolbar buttons to draw. Click a shape to select and drag to move.
                    Use trash icon to delete.
                </span>
                <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 text-xs"
                    onClick={() => {
                        drawRef.current?.deleteAll();
                        onChangeRef.current(null);
                    }}
                >
                    Clear all
                </Button>
            </div>
        </div>
    );
}
