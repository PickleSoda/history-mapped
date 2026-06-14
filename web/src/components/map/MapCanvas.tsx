import type { FeatureCollection } from 'geojson';
import type { GeoJSONSource } from 'maplibre-gl';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useRef } from 'react';
import { useEntitiesInView, useMapInstance, useTimeState, useViewport } from '@/hooks';
import { instantYear } from '@/lib/format';
import { loadHistoricalBasemapStyle } from '@/lib/map-config';
import { yearToOhmDate } from '@/lib/ohm-date';
import { applyOhmLayerDateFilter } from '@/lib/ohm-layer-date-filter';

const SOURCE_ID = 'entities';
const FILL_LAYER = 'entities-fill';
const LINE_LAYER = 'entities-line';
const CIRCLE_LAYER = 'entities-circles';
const EMPTY_FC: FeatureCollection = { type: 'FeatureCollection', features: [] };
const MOVE_DEBOUNCE_MS = 250;

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
    'PLACE', c('--g-place', '#2f7d6b'),
    'EVENT', c('--g-event', '#b07d23'),
    'ECONOMY', c('--g-economy', '#3f6db4'),
    'CULTURE', c('--g-culture', '#7a57ad'),
    // Literal hex default — maplibre cannot parse the oklch() theme tokens, so
    // never feed it --muted-foreground / other oklch vars here.
    '#71717a',
  ];
}

/**
 * The persistent map (spec §6). Mounts ONCE on the OpenHistoricalMap basemap,
 * whose time-aware vector layers are filtered to the active timeline year. The
 * camera/data are written imperatively; the map never re-renders to move.
 */
export function MapCanvas() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const { setMap } = useMapInstance();
  const { bbox, setBbox } = useViewport();
  const { time } = useTimeState();
  const { data } = useEntitiesInView();

  const year = instantYear(time);

  // Latest values for the (mount-once) init closure.
  const setBboxRef = useRef(setBbox);
  setBboxRef.current = setBbox;
  const yearRef = useRef(year);
  yearRef.current = year;
  const initialBboxRef = useRef(bbox);

  // ── init map once (async: the OHM style is fetched + normalized) ───────────
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let cancelled = false;
    let mapInstance: maplibregl.Map | null = null;
    let timer: ReturnType<typeof setTimeout>;

    loadHistoricalBasemapStyle().then((style) => {
      if (cancelled) return;

      const map = new maplibregl.Map({
        container,
        style,
        bounds: [
          [initialBboxRef.current.w, initialBboxRef.current.s],
          [initialBboxRef.current.e, initialBboxRef.current.n],
        ],
        attributionControl: { compact: true },
      });
      mapInstance = map;
      mapRef.current = map;

      map.on('load', () => {
        map.addSource(SOURCE_ID, { type: 'geojson', data: EMPTY_FC });

        const groupColor = groupColorExpression();

        // Entity territories (fill + outline) — drawn over the OHM basemap.
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
          id: CIRCLE_LAYER,
          type: 'circle',
          source: SOURCE_ID,
          filter: ['match', ['geometry-type'], ['Point', 'MultiPoint'], true, false],
          paint: {
            'circle-radius': 5,
            'circle-color': groupColor,
            'circle-stroke-width': 1,
            'circle-stroke-color': '#ffffff',
          },
        });

        // Filter the OHM basemap to the current year.
        applyOhmLayerDateFilter(map, yearToOhmDate(yearRef.current));
        setMap(map);
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
    };
    // Mount once. Camera/data/date sync happen in their own effects.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── re-filter the OHM basemap when the timeline year changes ───────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    applyOhmLayerDateFilter(map, yearToOhmDate(year));
  }, [year]);

  // ── push entity data imperatively when the query updates ───────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !data) return;
    const source = map.getSource(SOURCE_ID) as GeoJSONSource | undefined;
    source?.setData(data as FeatureCollection);
  }, [data]);

  return <div ref={containerRef} className="absolute inset-0 h-full w-full" />;
}
