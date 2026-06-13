import type { FeatureCollection } from 'geojson';
import type { GeoJSONSource } from 'maplibre-gl';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useRef } from 'react';
import { useEntitiesInView, useMapInstance, useViewport } from '@/hooks';

const SOURCE_ID = 'entities';
const FILL_LAYER = 'entities-fill';
const LINE_LAYER = 'entities-line';
const CIRCLE_LAYER = 'entities-circles';
const EMPTY_FC: FeatureCollection = { type: 'FeatureCollection', features: [] };
const BASEMAP_STYLE = 'https://demotiles.maplibre.org/style.json';
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
 * The persistent map (spec §6). It mounts ONCE and is never re-rendered to move
 * the camera — React writes data into it imperatively. Gestures commit the bbox
 * to the URL on settle; pins come from the same viewport query the list uses.
 */
export function MapCanvas() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const { setMap } = useMapInstance();
  const { bbox, setBbox } = useViewport();
  const { data } = useEntitiesInView();

  // Keep the latest setBbox in a ref so the moveend handler never goes stale.
  const setBboxRef = useRef(setBbox);
  setBboxRef.current = setBbox;

  // Initial camera from the URL bbox — read once on mount only.
  const initialBboxRef = useRef(bbox);

  // ── init map once ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: BASEMAP_STYLE,
      bounds: [
        [initialBboxRef.current.w, initialBboxRef.current.s],
        [initialBboxRef.current.e, initialBboxRef.current.n],
      ],
    });
    mapRef.current = map;

    map.on('load', () => {
      map.addSource(SOURCE_ID, { type: 'geojson', data: EMPTY_FC });

      const groupColor = groupColorExpression();

      // Polygon territories: fill + outline.
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
      // Point entities.
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
      setMap(map);
    });

    let timer: ReturnType<typeof setTimeout>;
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

    return () => {
      clearTimeout(timer);
      setMap(null);
      map.remove();
      mapRef.current = null;
    };
    // Mount once. Camera/data sync happen in their own effects.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── push entity data imperatively when the query updates ───────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !data) return;
    const source = map.getSource(SOURCE_ID) as GeoJSONSource | undefined;
    // The endpoint already returns a GeoJSON FeatureCollection — pass it straight
    // through (no client-side reserialization). Map features always carry
    // geometry, so the null-geometry case in the type never occurs here.
    source?.setData(data as FeatureCollection);
  }, [data]);

  return <div ref={containerRef} className="absolute inset-0 h-full w-full" />;
}
