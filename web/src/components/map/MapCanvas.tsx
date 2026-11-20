import type { FeatureCollection } from 'geojson';
import type { GeoJSONSource, ProjectionSpecification, StyleSpecification } from 'maplibre-gl';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useRef } from 'react';
import { EraLayer } from '@/components/era/EraLayer';
import { StoryAmbientLayer } from '@/components/map/StoryAmbientLayer';
import { StoryOverlay } from '@/components/map/StoryOverlay';
import {
  useBasemap,
  useEntitiesInView,
  useFilters,
  useFocusSet,
  useHover,
  useMapFocus,
  useMapInstance,
  useSelection,
  useTimeState,
  useView,
  useViewport,
} from '@/hooks';
import { instantYear } from '@/lib/format';
import { loadHistoricalBasemapStyle } from '@/lib/map-config';
import { pointsBounds } from '@/lib/map-focus';
import { registerGroupMarkers, refreshGroupMarkers, STORY_MARKER_ID } from '@/lib/map-icons';
import { STORY_SOURCES } from '@/lib/map-story/layers';
import {
  applyEntityLayerFilters,
  ENTITY_SOURCE_LAYER,
  entityTileSource,
  isMapTilesEnabled,
  isPoint,
  isPolygon,
  SOURCE_ID,
} from '@/lib/map-tiles';
import { yearToOhmDate } from '@/lib/ohm-date';
import {
  addOhmAdminLayers,
  hoverMarkerData,
  LINK_COLOR,
  OhmCorrelation,
} from '@/lib/ohm-highlight';
import { applyOhmLayerDateFilter } from '@/lib/ohm-layer-date-filter';
import { resolveOhmClickToEntity } from '@/lib/ohm-resolve';
import { useTheme } from '@/lib/theme';
import { useEphemeralStore } from '@/stores/ephemeral';
import type { ViewMode } from '@/types/atlas';

const FILL_LAYER = 'entities-fill';
const LINE_LAYER = 'entities-line';
const SYMBOL_LAYER = 'entities-symbols';
/** The hovered entity's marker, drawn larger over SYMBOL_LAYER (D5), from
 *  its own one-feature GeoJSON source. */
const HOVER_LAYER = 'entities-hover';
const HOVER_SOURCE = 'entities-hover-src';
/** The focused set (an entity's relations, or a search word's matches), from
 *  its own GeoJSON source; while it shows, the three layers above are emptied. */
const FOCUS_LAYER = 'entities-focus';
const FOCUS_SOURCE = 'entities-focus-src';
/** Matches nothing: empties a layer without touching its visibility (which
 *  the battle map toggles). */
const NOTHING: maplibregl.FilterSpecification = ['==', ['literal', 1], 0];
/** Rebuild the OHM link index this long after our source's last tile. */
const LINK_INDEX_DEBOUNCE_MS = 150;
/** Our three layers, for the tile-mode time / group filters. */
const ENTITY_LAYERS = { fill: FILL_LAYER, line: LINE_LAYER, symbol: SYMBOL_LAYER };
const EMPTY_FC: FeatureCollection = { type: 'FeatureCollection', features: [] };
const MOVE_DEBOUNCE_MS = 250;

/** Layers a user can click to select the underlying entity. */
const INTERACTIVE_LAYERS = [FOCUS_LAYER, SYMBOL_LAYER, FILL_LAYER];

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
  // Tile mode (VITE_MAP_TILES_URL): all-time vector tiles, filtered per layer
  // by applyEntityLayerFilters; otherwise the viewport GeoJSON.
  const tiles = isMapTilesEnabled();
  map.addSource(
    SOURCE_ID,
    tiles ? entityTileSource() : { type: 'geojson', data: data ?? EMPTY_FC },
  );
  const sourceLayer = tiles ? { 'source-layer': ENTITY_SOURCE_LAYER } : {};

  const groupColor = groupColorExpression();

  // Entity territories (fill + outline) — drawn over the OHM basemap.
  map.addLayer({
    id: FILL_LAYER,
    type: 'fill',
    source: SOURCE_ID,
    ...sourceLayer,
    filter: isPolygon,
    paint: { 'fill-color': groupColor, 'fill-opacity': 0.15 },
  });
  map.addLayer({
    id: LINE_LAYER,
    type: 'line',
    source: SOURCE_ID,
    ...sourceLayer,
    filter: isPolygon,
    paint: { 'line-color': groupColor, 'line-width': 1 },
  });

  // Marker icon, shared by the symbol and hover layers: the battle-map pin
  // for an entity with a map story (REST and tile `has_map_story`), else its
  // group icon. A playable battle map also gets a slightly larger pin.
  const hasMapStory: maplibregl.ExpressionSpecification = ['==', ['get', 'has_map_story'], true];
  const markerIcon: maplibregl.ExpressionSpecification = [
    'case',
    hasMapStory,
    ['image', STORY_MARKER_ID],
    [
      'coalesce',
      ['image', ['concat', 'marker-', ['get', 'entity_group']]],
      ['image', 'marker-DEFAULT'],
    ],
  ];

  // Points (OHM-linked / unplaced entities) — group icon + label.
  map.addLayer({
    id: SYMBOL_LAYER,
    type: 'symbol',
    source: SOURCE_ID,
    ...sourceLayer,
    filter: isPoint,
    layout: {
      'icon-image': markerIcon,
      'icon-size': ['case', hasMapStory, 0.95, 0.8],
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
      // light-map colors regardless of the app theme. OHM-linked entities
      // (tile `ohm_osm_id` / REST `ohm_external_id`) take the link colour.
      'text-color': [
        'case',
        ['!=', ['coalesce', ['get', 'ohm_osm_id'], ['get', 'ohm_external_id']], null],
        LINK_COLOR,
        '#2a2722',
      ],
      'text-halo-color': '#ffffff',
      'text-halo-width': 1.4,
    },
  });

  // The focused set. Nearer relations are larger and labelled first; every
  // marker shows at any zoom (nothing here depends on the impact threshold).
  const depth: maplibregl.ExpressionSpecification = ['coalesce', ['get', 'depth'], 0];
  map.addSource(FOCUS_SOURCE, { type: 'geojson', data: EMPTY_FC });
  map.addLayer({
    id: FOCUS_LAYER,
    type: 'symbol',
    source: FOCUS_SOURCE,
    layout: {
      'icon-image': markerIcon,
      'icon-size': ['match', depth, 0, 1.05, 1, 0.85, 0.62],
      'icon-allow-overlap': true,
      'icon-anchor': 'bottom',
      'symbol-sort-key': ['-', ['*', depth, 1000], ['coalesce', ['get', 'impact_score'], 0]],
      'text-field': ['get', 'name'],
      'text-size': ['match', depth, 0, 12.5, 1, 11, 10],
      'text-offset': [0, 0.4],
      'text-anchor': 'top',
      'text-optional': true,
      'text-max-width': 8,
    },
    paint: {
      'icon-opacity': ['match', depth, 2, 0.8, 1],
      'text-color': '#2a2722',
      'text-halo-color': '#ffffff',
      'text-halo-width': 1.4,
    },
  });

  // The hovered entity's marker (list <-> map hover, D5): a copy of its
  // point in a one-feature source, updated with setData. Not feature-state
  // (MapLibre rejects it in layout properties such as icon-size; the marker
  // images are not SDF) and not setFilter (that reloads our whole source).
  map.addSource(HOVER_SOURCE, { type: 'geojson', data: EMPTY_FC });
  map.addLayer({
    id: HOVER_LAYER,
    type: 'symbol',
    source: HOVER_SOURCE,
    layout: {
      'icon-image': markerIcon,
      'icon-size': ['case', hasMapStory, 1.2, 1.05],
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
      'icon-anchor': 'bottom',
    },
  });
}

/** Point the hover source at `hoverId`'s marker for `year` (or at nothing). */
function showHoveredMarker(
  map: maplibregl.Map,
  hoverId: string | null,
  year: number,
  data: FeatureCollection | undefined,
  focus: FeatureCollection | undefined,
): void {
  const source = map.getSource(HOVER_SOURCE) as GeoJSONSource | undefined;
  if (!source) return;
  const candidates =
    hoverId === null
      ? []
      : focus
        ? focus.features
        : isMapTilesEnabled()
          ? map.querySourceFeatures(SOURCE_ID, {
              sourceLayer: ENTITY_SOURCE_LAYER,
              filter: ['==', ['get', 'id'], hoverId],
            })
          : (data?.features ?? []);
  source.setData(hoverMarkerData(candidates, hoverId, year));
}

/**
 * Filter our fill / outline / symbol layers: to nothing while a focused set
 * shows in their place, else to their geometry type (and, in tile mode, the
 * timeline year and the group filter).
 */
function applyBaseFilters(
  map: maplibregl.Map,
  focused: boolean,
  time: Parameters<typeof applyEntityLayerFilters>[1]['time'],
  groups: Parameters<typeof applyEntityLayerFilters>[1]['groups'],
): void {
  if (!focused && isMapTilesEnabled()) {
    applyEntityLayerFilters(map, { layers: ENTITY_LAYERS, time, groups });
    return;
  }
  const targets: [string, maplibregl.FilterSpecification][] = [
    [FILL_LAYER, focused ? NOTHING : isPolygon],
    [LINE_LAYER, focused ? NOTHING : isPolygon],
    [SYMBOL_LAYER, focused ? NOTHING : isPoint],
  ];
  for (const [id, filter] of targets) {
    if (map.getLayer(id)) map.setFilter(id, filter);
  }
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
  const { groups } = useFilters();
  const { sel, select } = useSelection();
  const { hoverId, setHover } = useHover();
  const { data } = useEntitiesInView();
  const { target: focusTarget, data: focusData, settled: focusSettled } = useFocusSet();
  const { focusBounds } = useMapFocus();
  const theme = useTheme((s) => s.theme);

  const year = instantYear(time);

  // Latest values for the (mount-once) init closure.
  const setBboxRef = useRef(setBbox);
  setBboxRef.current = setBbox;
  const selectRef = useRef(select);
  selectRef.current = select;
  const selRef = useRef(sel);
  selRef.current = sel;
  const setHoverRef = useRef(setHover);
  setHoverRef.current = setHover;
  /** OHM correlation state of the live map (D5); null until it exists. */
  const correlationRef = useRef<OhmCorrelation | null>(null);
  const yearRef = useRef(year);
  yearRef.current = year;
  const timeRef = useRef(time);
  timeRef.current = time;
  const groupsRef = useRef(groups);
  groupsRef.current = groups;
  const dataRef = useRef(data);
  dataRef.current = data;
  /** The focused set on the map, or undefined when the viewport's own shows. */
  const focusRef = useRef(focusData);
  focusRef.current = focusData;
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
    let linkTimer: ReturnType<typeof setTimeout> | undefined;

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
      const correlation = new OhmCorrelation(map);
      correlationRef.current = correlation;

      // Every style load — the first, and each basemap switch, which replaces
      // the whole style — re-adds marker icons and our overlay, then filters
      // the new basemap's OHM layers to the current year.
      map.on('style.load', async () => {
        const loading = map.style;
        await registerGroupMarkers(map);
        // Unmounted, or superseded by another switch while the icons loaded.
        if (cancelled || map.style !== loading) return;

        addEntityLayers(map, dataRef.current as FeatureCollection | undefined);
        const focus = focusRef.current as FeatureCollection | undefined;
        (map.getSource(FOCUS_SOURCE) as GeoJSONSource | undefined)?.setData(focus ?? EMPTY_FC);
        applyBaseFilters(map, focus !== undefined, timeRef.current, groupsRef.current);
        // OHM correlation (D5): polygon highlight layers under ours, then
        // labels / emphasis / hovered marker re-applied to the new style.
        addOhmAdminLayers(map, FILL_LAYER);
        const hovered = useEphemeralStore.getState().hoverId;
        correlation.styleLoaded(hovered, selRef.current);
        showHoveredMarker(
          map,
          hovered,
          yearRef.current,
          dataRef.current as FeatureCollection | undefined,
          focusRef.current as FeatureCollection | undefined,
        );
        // Catch up on a Map/Globe toggle made while the style was loading.
        map.setProjection(projectionFor(viewRef.current));
        applyOhmLayerDateFilter(map, yearToOhmDate(yearRef.current));
        styleReadyRef.current = true;
        setMap(map);
        // Tell other overlays (the battle map) to re-add their layers on top.
        useEphemeralStore.getState().bumpStyleEpoch();
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

        // During a battle map the basemap isn't clickable: its own layers
        // handle clicks on units, and stray clicks shouldn't open entities.
        if (map.getSource(STORY_SOURCES.units)) return;

        const seq = ++clickSeq;
        void resolveOhmClickToEntity(map, e, yearRef.current).then(
          (entityId) => {
            // A layer that claimed the click (an ambient story's card) wins.
            if (entityId && seq === clickSeq && !e.defaultPrevented) void selectRef.current(entityId);
          },
        );
      });

      // OHM correlation (D5): rebuild the osm-id → entity index once our
      // source settles (tiles stream in; GeoJSON is replaced per viewport).
      map.on('sourcedata', (e) => {
        if (e.sourceId !== SOURCE_ID) return;
        clearTimeout(linkTimer);
        linkTimer = setTimeout(() => {
          if (!styleReadyRef.current || !map.getSource(SOURCE_ID)) return;
          if (!map.isSourceLoaded(SOURCE_ID)) return;
          // A focused set is indexed by its own effect.
          if (focusRef.current) return;
          correlation.setFeatures(
            isMapTilesEnabled()
              ? map.querySourceFeatures(SOURCE_ID, {
                  sourceLayer: ENTITY_SOURCE_LAYER,
                  filter: ['has', 'ohm_osm_id'],
                })
              : ((dataRef.current as FeatureCollection | undefined)?.features ?? []),
          );
        }, LINK_INDEX_DEBOUNCE_MS);
      });

      // Map side of the hover sync: our marker, else a linked OHM label,
      // writes hoverId. Cleared only if this map set it, so a list row's
      // hover is never wiped by the map.
      let mapHover: string | null = null;
      const setMapHover = (id: string | null) => {
        if (id === mapHover) return;
        if (id !== null || useEphemeralStore.getState().hoverId === mapHover) {
          setHoverRef.current(id);
        }
        mapHover = id;
      };
      map.on('mousemove', (e) => {
        if (!styleReadyRef.current) return;
        // During a battle map our markers are hidden and OHM labels are not
        // hover targets either (as with clicks above).
        if (map.getSource(STORY_SOURCES.units)) {
          setMapHover(null);
          return;
        }
        setMapHover(correlation.entityAt(e.point, focusRef.current ? FOCUS_LAYER : SYMBOL_LAYER));
      });
      map.on('mouseout', () => setMapHover(null));
      // Idle OHM polygon layers go before the new view fetches their tiles.
      map.on('moveend', () => correlation.viewMoved());

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
      clearTimeout(linkTimer);
      correlationRef.current?.dispose();
      correlationRef.current = null;
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

  // ── tile mode: filter our layers by time + groups client-side (D1) ─────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReadyRef.current || !isMapTilesEnabled()) return;
    applyBaseFilters(map, focusRef.current !== undefined, time, groups);
  }, [time, groups]);

  // ── the focused set: an entity's relations, or a search word's matches ─────
  // It replaces the viewport's own markers and shows whole at any zoom.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReadyRef.current) return;
    const focus = focusData as FeatureCollection | undefined;
    (map.getSource(FOCUS_SOURCE) as GeoJSONSource | undefined)?.setData(focus ?? EMPTY_FC);
    applyBaseFilters(map, focus !== undefined, timeRef.current, groupsRef.current);
    // OHM labels and polygons follow the set on the map.
    correlationRef.current?.setFeatures(
      focus
        ? focus.features
        : isMapTilesEnabled()
          ? map.querySourceFeatures(SOURCE_ID, {
              sourceLayer: ENTITY_SOURCE_LAYER,
              filter: ['has', 'ohm_osm_id'],
            })
          : ((dataRef.current as FeatureCollection | undefined)?.features ?? []),
    );
  }, [focusData, loadedMap]);

  // Frame a newly focused set once: a search word's matches, or the relations
  // of an entity with no place of its own (a person). A placed entity is
  // framed by its detail panel, with its relations around it.
  const framedRef = useRef<string | null>(null);
  useEffect(() => {
    if (!focusTarget) {
      framedRef.current = null;
      return;
    }
    if (!focusSettled || !focusData || !loadedMap) return;
    const key = JSON.stringify(focusTarget);
    if (framedRef.current === key) return;
    framedRef.current = key;
    const rootPlaced =
      focusTarget.kind === 'related' && focusData.features.some((f) => f.properties.id === focusTarget.id.toLowerCase());
    if (rootPlaced) return;
    // Direct relations frame a person; the second hop only adds context.
    const near = focusData.features.filter((f) => (f.properties.depth ?? 0) <= 1);
    const points = (near.length > 0 ? near : focusData.features)
      .map((f) => (f.geometry?.type === 'Point' ? (f.geometry.coordinates as [number, number]) : null))
      .filter((p): p is [number, number] => p !== null);
    focusBounds(pointsBounds(points));
  }, [focusTarget, focusSettled, focusData, loadedMap, focusBounds]);

  // ── correlation: the hovered entity's marker (both modes, D5) ──────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReadyRef.current) return;
    showHoveredMarker(
      map,
      hoverId,
      yearRef.current,
      dataRef.current as FeatureCollection | undefined,
      focusRef.current as FeatureCollection | undefined,
    );
  }, [hoverId]);

  // ── correlation: OHM polygon of the hovered / selected entity (D5) ─────────
  useEffect(() => {
    if (!styleReadyRef.current) return;
    correlationRef.current?.emphasize(hoverId, sel);
  }, [hoverId, sel]);

  // ── push entity data imperatively when the query updates ───────────────────
  useEffect(() => {
    const map = mapRef.current;
    // Tile mode has no GeoJSON to push (and the viewport query is off).
    if (!map || !data || isMapTilesEnabled()) return;
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

  return (
    <>
      <div ref={containerRef} className="absolute inset-0 h-full w-full" />
      <EraLayer />
      <StoryOverlay />
      <StoryAmbientLayer />
    </>
  );
}
