/**
 * Pure geometry → camera-bounds helpers for "focus" (framing an entity, or a
 * whole chronicle step's cast, on the map). Kept free of maplibre so it can be
 * unit-tested; the `useMapFocus` hook turns these bounds into flyTo/fitBounds.
 *
 * Geometry arrives as `unknown` (the schemas keep `geom` permissive), so the
 * walkers are runtime-tolerant: Point / Line / Polygon / Multi*, plus Feature
 * and GeometryCollection wrappers. Antimeridian-crossing spans are not handled
 * (rare for our dataset) — the union box just gets wide.
 */

/** [[minLng, minLat], [maxLng, maxLat]] — a maplibre `LngLatBoundsLike`. */
export type FocusBounds = [[number, number], [number, number]];

interface Acc {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

/** Recurse a GeoJSON coordinate array (Position | Position[] | …), extending acc. */
function walkCoords(node: unknown, acc: Acc): void {
  if (!Array.isArray(node)) return;
  if (typeof node[0] === 'number' && typeof node[1] === 'number') {
    const [x, y] = node as [number, number];
    if (Number.isFinite(x) && Number.isFinite(y)) {
      if (x < acc.minX) acc.minX = x;
      if (y < acc.minY) acc.minY = y;
      if (x > acc.maxX) acc.maxX = x;
      if (y > acc.maxY) acc.maxY = y;
    }
    return;
  }
  for (const child of node) walkCoords(child, acc);
}

/** Extend acc with one GeoJSON geometry / Feature / GeometryCollection. */
function walkGeometry(geom: unknown, acc: Acc): void {
  if (!geom || typeof geom !== 'object') return;
  const g = geom as {
    type?: string;
    coordinates?: unknown;
    geometries?: unknown;
    geometry?: unknown;
  };
  if (g.type === 'Feature') {
    walkGeometry(g.geometry, acc);
    return;
  }
  if (g.type === 'GeometryCollection' && Array.isArray(g.geometries)) {
    for (const sub of g.geometries) walkGeometry(sub, acc);
    return;
  }
  if (g.coordinates != null) walkCoords(g.coordinates, acc);
}

/**
 * Union bounds over any number of GeoJSON geometries (nulls / non-geometries
 * ignored). Returns null when none carry a usable coordinate — the caller
 * should then do nothing rather than fly to a bogus location.
 */
export function geometriesBounds(geoms: unknown[]): FocusBounds | null {
  const acc: Acc = {
    minX: Infinity,
    minY: Infinity,
    maxX: -Infinity,
    maxY: -Infinity,
  };
  for (const geom of geoms) walkGeometry(geom, acc);
  if (!Number.isFinite(acc.minX) || !Number.isFinite(acc.minY)) return null;
  return [
    [acc.minX, acc.minY],
    [acc.maxX, acc.maxY],
  ];
}

/** True when the bounds collapse to a single point — fitBounds would over-zoom. */
export function isPointBounds(b: FocusBounds): boolean {
  return b[0][0] === b[1][0] && b[0][1] === b[1][1];
}
