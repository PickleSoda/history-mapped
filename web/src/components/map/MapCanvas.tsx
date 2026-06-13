import type { FeatureCollection, Point } from 'geojson';
import maplibregl, { GeoJSONSource } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useRef } from 'react';
import { useEntitiesInView, useMapInstance, useViewport } from '@/hooks';
import type { EntitySummary } from '@/lib/schemas/entity';

const SOURCE_ID = 'entities';
const LAYER_ID = 'entities-circles';
const BASEMAP_STYLE = 'https://demotiles.maplibre.org/style.json';
const MOVE_DEBOUNCE_MS = 250;

/** Build a point FeatureCollection from placed entities (skips null geometry). */
function toFeatureCollection(items: EntitySummary[]): FeatureCollection<Point> {
  return {
    type: 'FeatureCollection',
    features: items
      .filter((e): e is EntitySummary & { point: [number, number] } => e.point !== null)
      .map((e) => ({
        type: 'Feature',
        id: e.id,
        geometry: { type: 'Point', coordinates: e.point },
        properties: { id: e.id, group: e.group, name: e.name },
      })),
  };
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
      map.addSource(SOURCE_ID, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
      map.addLayer({
        id: LAYER_ID,
        type: 'circle',
        source: SOURCE_ID,
        paint: {
          'circle-radius': 5,
          'circle-color': '#2563eb',
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
    source?.setData(toFeatureCollection(data.items));
  }, [data]);

  return <div ref={containerRef} className="absolute inset-0 h-full w-full" />;
}
