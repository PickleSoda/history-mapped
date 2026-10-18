import type { FeatureCollection } from 'geojson';
import type { GeoJSONSource, ProjectionSpecification, StyleSpecification } from 'maplibre-gl';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useRef } from 'react';
import {
  useBasemap,
  useEntitiesInView,
  useMapInstance,
  useSelection,
  useTimeState,
  useView,
  useViewport,
} from '@/hooks';
import { instantYear } from '@/lib/format';
import { loadHistoricalBasemapStyle } from '@/lib/map-config';
import { registerGroupMarkers, refreshGroupMarkers } from '@/lib/map-icons';
import { yearToOhmDate } from '@/lib/ohm-date';
import { applyOhmLayerDateFilter } from '@/lib/ohm-layer-date-filter';
import { resolveOhmClickToEntity } from '@/lib/ohm-resolve';
import { useTheme } from '@/lib/theme';
import type { ViewMode } from '@/types/atlas';

const SOURCE_ID = 'entities';
const FILL_LAYER = 'entities-fill';
const LINE_LAYER = 'entities-line';
const SYMBOL_LAYER = 'entities-symbols';
const EMPTY_FC: FeatureCollection = { type: 'FeatureCollection', features: [] };
const MOVE_DEBOUNCE_MS = 250;

/** Layers a user can click to select the underlying entity. */
const INTERACTIVE_LAYERS = [SYMBOL_LAYER, FILL_LAYER];

/** The URL `view` as a maplibre projection. The globe flattens back to
 *  mercator on its own as the camera zooms in. */
function projectionFor(view: ViewMode): ProjectionSpecification {
  return { type: view === 'globe' ? 'globe' : 'mercator' };
}

/** A basemap style set to open in the given projection. */
function withProjection(style: StyleSpecification, view: ViewMode): StyleSpecification {
  return { ...style, projection: projectionFor(view) };
}

/**
 * Resolve the active theme's group palette into a maplibre `match` expression
 * keyed on the feature's UPPERCASE entity_group, so the map tracks the theme.
 */
function groupColorExpression(): maplibregl.ExpressionSpecification {
  const root = getComputedStyle(document.documentElement);
  const c = (name: string, fallback: string) =>
    root.getPropertyValue(name).trim() || fallback;
  return [
    'match',
    ['get', 'entity_group'],
    'POLITY', c('--g-polity', '#b4543f'),
    'PLACE', c('--g-place', '#6b7f4a'),
    'EVENT', c('--g-event', '#bd8a2c'),
    'ECONOMY', c('--g-economy', '#4d6a86'),
    'CULTURE', c('--g-culture', '#8a5673'),
    // Literal hex default — maplibre cannot parse the oklch() theme tokens, so
    // never feed it --muted-foreground / other oklch vars here.
    '#71717a',
  ];
}

/**
 * Our entity overlay — source plus fill / outline / symbol layers — drawn over
 * whichever basemap is loaded. Group marker icons must be registered first.
 */
function addEntityLayers(map: maplibregl.Map, data: FeatureCollection | undefined): void {
  map.addSource(SOURCE_ID, { type: 'geojson', data: data ?? EMPTY_FC });

  const groupColor = groupColorExpression();
  const isPolygon: maplibregl.FilterSpecification = [
    'match', ['geometry-type'], ['Polygon', 'MultiPolygon'], true, false,
  ];
  const isPoint: maplibregl.FilterSpecification = [
    'match', ['geometry-type'], ['Point', 'MultiPoint'], true, false,
  ];

  // Entity territories (fill + outline) — drawn over the OHM basemap.
  map.addLayer({
    id: FILL_LAYER,
    type: 'fill',
    source: SOURCE_ID,
    filter: isPolygon,
    paint: { 'fill-color': groupColor, 'fill-opacity': 0.15 },
  });
  map.addLayer({
    id: LINE_LAYER,
    type: 'line',
    source: SOURCE_ID,
    filter: isPolygon,
    paint: { 'line-color': groupColor, 'line-width': 1 },
  });

  // Points (OHM-linked / unplaced entities) — group icon + label.
  map.addLayer({
    id: SYMBOL_LAYER,
    type: 'symbol',
    source: SOURCE_ID,
    filter: isPoint,
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
      // Every OHM basemap is light in both UI themes, so map labels keep
      // light-map colors regardless of the app theme.
      'text-color': '#2a2722',
      'text-halo-color': '#ffffff',
      'text-halo-width': 1.4,
    },
  });
}

/**
 * The persistent map (spec §6). Mounts ONCE on an OpenHistoricalMap basemap
 * (URL `base`), whose time-aware vector layers are filtered to the active
 * timeline year. The camera/data are written imperatively; the map never
 * re-renders to move. A basemap switch swaps the whole style and re-adds the
 * entity overlay on top.
 */
export function MapCanvas() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  // Published once the first style and our overlay are in, so it doubles as
  // the "map is ready" signal for the projection / basemap effects.
  const { map: loadedMap, setMap } = useMapInstance();
  const { view } = useView();
  const { basemap } = useBasemap();
  const { bbox, setBbox } = useViewport();
  const { time } = useTimeState();
  const { select } = useSelection();
  const { data } = useEntitiesInView();
  const theme = useTheme((s) => s.theme);

  const year = instantYear(time);

  // Latest values for the (mount-once) init closure.
  const setBboxRef = useRef(setBbox);
  setBboxRef.current = setBbox;
  const selectRef = useRef(select);
  selectRef.current = select;
  const yearRef = useRef(year);
  yearRef.current = year;
  const dataRef = useRef(data);
  dataRef.current = data;
  const viewRef = useRef(view);
  viewRef.current = view;
  const initialBboxRef = useRef(bbox);
  /** The basemap the current (or loading) style was built from. */
  const appliedBasemapRef = useRef(basemap);
  /** False from `setStyle` until the new style's overlay is in: style setters
   *  (filters, projection) throw while a style is loading. Unlike
   *  `isStyleLoaded()`, it stays true while tiles stream in. */
  const styleReadyRef = useRef(false);

  // ── init map once (async: the OHM style is fetched + normalized) ───────────
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let cancelled = false;
    let mapInstance: maplibregl.Map | null = null;
    let timer: ReturnType<typeof setTimeout>;

    loadHistoricalBasemapStyle(appliedBasemapRef.current).then((style) => {
      if (cancelled) return;

      const map = new maplibregl.Map({
        container,
        // Start in the URL's projection so a shared globe link opens as one.
        style: withProjection(style, viewRef.current),
        bounds: [
          [initialBboxRef.current.w, initialBboxRef.current.s],
          [initialBboxRef.current.e, initialBboxRef.current.n],
        ],
        attributionControl: { compact: true },
      });
      mapInstance = map;
      mapRef.current = map;

      // Every style load — the first, and each basemap switch, which replaces
      // the whole style — re-adds marker icons and our overlay, then filters
      // the new basemap's OHM layers to the current year.
      map.on('style.load', async () => {
        const loading = map.style;
        await registerGroupMarkers(map);
        // Unmounted, or superseded by another switch while the icons loaded.
        if (cancelled || map.style !== loading) return;

        addEntityLayers(map, dataRef.current as FeatureCollection | undefined);
        // Catch up on a Map/Globe toggle made while the style was loading.
        map.setProjection(projectionFor(viewRef.current));
        applyOhmLayerDateFilter(map, yearToOhmDate(yearRef.current));
        styleReadyRef.current = true;
        setMap(map);
      });

      // Pointer cursor over our own clickable features. Layer-scoped handlers
      // live on the map, so they survive style swaps.
      const setPointer = () => {
        map.getCanvas().style.cursor = 'pointer';
      };
      const clearPointer = () => {
        map.getCanvas().style.cursor = '';
      };
      for (const layerId of INTERACTIVE_LAYERS) {
        map.on('mouseenter', layerId, setPointer);
        map.on('mouseleave', layerId, clearPointer);
      }

      // Unified click: select a clicked entity; otherwise try resolving an
      // OHM basemap feature under the click to one of our entities. A click
      // sequence token drops a stale resolution if the user clicks again.
      let clickSeq = 0;
      map.on('click', (e) => {
        const layers = INTERACTIVE_LAYERS.filter((l) => map.getLayer(l));
        const hit = layers.length
          ? map.queryRenderedFeatures(e.point, { layers })[0]
          : undefined;
        const id = hit?.properties?.id;
        if (typeof id === 'string' && id) {
          void selectRef.current(id);
          return;
        }

        const seq = ++clickSeq;
        void resolveOhmClickToEntity(map, e, yearRef.current).then(
          (entityId) => {
            if (entityId && seq === clickSeq) void selectRef.current(entityId);
          },
        );
      });

      const onMoveEnd = () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          const b = map.getBounds();
          setBboxRef.current({
            w: b.getWest(),
            s: b.getSouth(),
            e: b.getEast(),
            n: b.getNorth(),
          });
        }, MOVE_DEBOUNCE_MS);
      };
      map.on('moveend', onMoveEnd);
    });

    return () => {
      cancelled = true;
      clearTimeout(timer);
      setMap(null);
      mapInstance?.remove();
      mapRef.current = null;
      styleReadyRef.current = false;
    };
    // Mount once. Camera/data/date sync happen in their own effects.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── swap the basemap style when the Layers choice changes ──────────────────
  useEffect(() => {
    if (!loadedMap || basemap === appliedBasemapRef.current) return;
    let stale = false;
    void loadHistoricalBasemapStyle(basemap).then((style) => {
      if (stale) return;
      appliedBasemapRef.current = basemap;
      styleReadyRef.current = false;
      // A full rebuild, not a diff: the styles share layer ids but little
      // else, and the rebuild fires 'style.load', which re-adds our overlay.
      loadedMap.setStyle(withProjection(style, viewRef.current), { diff: false });
    });
    return () => {
      stale = true;
    };
  }, [loadedMap, basemap]);

  // ── follow the Map / Globe toggle ───────────────────────────────────────────
  useEffect(() => {
    if (loadedMap && styleReadyRef.current) {
      loadedMap.setProjection(projectionFor(view));
    }
  }, [loadedMap, view]);

  // ── re-filter the OHM basemap when the timeline year changes ───────────────
  useEffect(() => {
    const map = mapRef.current;
    // Not isStyleLoaded(): that is false whenever tiles are in flight, which
    // would drop the change. A style still loading picks up the year itself.
    if (!map || !styleReadyRef.current) return;
    applyOhmLayerDateFilter(map, yearToOhmDate(year));
  }, [year]);

  // ── push entity data imperatively when the query updates ───────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !data) return;
    const source = map.getSource(SOURCE_ID) as GeoJSONSource | undefined;
    source?.setData(data as FeatureCollection);
  }, [data]);

  // ── recolor overlays when the theme changes (WebGL can't read CSS vars) ─────
  useEffect(() => {
    const map = mapRef.current;
    // No isStyleLoaded() gate here: it's false whenever ANY tiles are in
    // flight (common during pan/zoom), which would silently skip the recolor
    // with nothing to re-fire it later. Every mutation below is already
    // guarded by map.getLayer(...), so a bare map-exists check is sufficient.
    if (!map) return;
    const groupColor = groupColorExpression();
    if (map.getLayer(FILL_LAYER)) {
      map.setPaintProperty(FILL_LAYER, 'fill-color', groupColor);
    }
    if (map.getLayer(LINE_LAYER)) {
      map.setPaintProperty(LINE_LAYER, 'line-color', groupColor);
    }
    // Symbol label colors stay fixed: the basemap is light in both UI themes.
    void refreshGroupMarkers(map);
  }, [theme]);

  return <div ref={containerRef} className="absolute inset-0 h-full w-full" />;
}
