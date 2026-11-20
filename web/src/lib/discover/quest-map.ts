/**
 * The daily expedition's eyes and hands on the map: how far the target lies
 * from the middle of what the reader can see, whether it is in view, how wide
 * that view is, and the flight of "Take me there".
 *
 * Everything is measured on screen, over the part of the map the floating
 * panels leave visible (`mapInsets`), so it holds whatever the camera's
 * padding, on a turned or tilted map, on the globe and across the date line.
 * The map is taken as a handful of methods, so a test can stand in for it.
 */
import type { MapInsets } from '@/types/atlas';
import { compassBearing, distanceKm, REGIONAL_KM } from './quest';
import type { LngLat, MapView } from './quest';

/** The part of a `maplibregl.Map` used here. */
export interface QuestMap {
  getContainer(): { clientWidth: number; clientHeight: number };
  project(lngLat: LngLat): { x: number; y: number };
  unproject(point: [number, number]): { lng: number; lat: number };
  getBearing(): number;
  getZoom(): number;
  flyTo(options: {
    center: LngLat;
    zoom: number;
    padding: { top: number; right: number; bottom: number; left: number };
    duration: number;
  }): unknown;
}

/** A box on the map's container, in pixels from its top left corner. */
export interface Rect {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

/** Less than this left of the map (a sheet pulled right up) is nothing to look at. */
const MIN_VISIBLE_PX = 48;
/** Room between the target and the edge of the visible map, so its marker
 *  shows whole; more at the top, where the strip sits (on two lines on a
 *  map as narrow as a phone's). */
const MARGIN = { top: 64, topNarrow: 100, side: 24, bottom: 24 };
/** Below this width the strip wraps (Tailwind's `sm`). */
const NARROW_PX = 640;

const whole = (width: number, height: number): Rect => ({ left: 0, top: 0, right: width, bottom: height });

/** The part of a map `width` × `height` px that the panels leave visible; null when they cover it. */
export function visibleRect(width: number, height: number, insets: MapInsets | null): Rect | null {
  if (!insets) return whole(width, height);
  const rect = {
    left: insets.left * width,
    top: insets.top * height,
    right: width - insets.right * width,
    bottom: height - insets.bottom * height,
  };
  return rect.right - rect.left >= MIN_VISIBLE_PX && rect.bottom - rect.top >= MIN_VISIBLE_PX ? rect : null;
}

/** Where the target must be to count as in view: the visible part of a map
 *  `mapWidth` px wide, less its margins (all of it when it is too small to
 *  give them up). */
export function arrivalRect(visible: Rect, mapWidth: number): Rect {
  const rect = {
    left: visible.left + MARGIN.side,
    top: visible.top + (mapWidth < NARROW_PX ? MARGIN.topNarrow : MARGIN.top),
    right: visible.right - MARGIN.side,
    bottom: visible.bottom - MARGIN.bottom,
  };
  return rect.right - rect.left >= MIN_VISIBLE_PX && rect.bottom - rect.top >= MIN_VISIBLE_PX ? rect : visible;
}

export function rectContains(rect: Rect, x: number, y: number): boolean {
  return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
}

/** Km across one pixel at zoom 0 on the equator (512-px tiles, as MapLibre counts zoom). */
const KM_PER_PX = 40_075.017 / 512;

/** The zoom at which `px` pixels span `km` at a latitude. */
export function zoomForSpan(lat: number, px: number, km: number): number {
  return Math.log2((KM_PER_PX * Math.cos((lat * Math.PI) / 180) * px) / km);
}

/** The flat map repeats the world sideways: the target may be on screen a turn away. */
const WORLD_TURNS = [0, -360, 360];

const point = ({ lng, lat }: { lng: number; lat: number }): LngLat => [lng, lat];

/**
 * What the map shows of a target at `at`. Null while the map has no size.
 * With the map covered whole the distances are still measured (from its
 * middle), but nothing counts as in view.
 */
export function readMapView(map: QuestMap, insets: MapInsets | null, at: LngLat): MapView | null {
  const { clientWidth: width, clientHeight: height } = map.getContainer();
  if (!width || !height) return null;
  const visible = visibleRect(width, height, insets);
  const rect = visible ?? whole(width, height);
  const middle = point(map.unproject([(rect.left + rect.right) / 2, (rect.top + rect.bottom) / 2]));
  const km = distanceKm(middle, at);
  // Corner to middle to corner: each half goes the short way round the world
  // however wide the view is, where corner to corner might not.
  const diagonalKm =
    distanceKm(point(map.unproject([rect.left, rect.top])), middle) +
    distanceKm(middle, point(map.unproject([rect.right, rect.bottom])));
  const zone = visible ? arrivalRect(visible, width) : null;
  const onScreen =
    zone != null &&
    WORLD_TURNS.some((turn) => {
      const p = map.project([at[0] + turn, at[1]]);
      return rectContains(zone, p.x, p.y);
    });
  const bearing = compassBearing(middle, at);
  return {
    km,
    diagonalKm,
    // On the globe a point on the far side still lands on the screen; a point
    // truly in view is never farther from the middle than the view is wide.
    inView: onScreen && km <= diagonalKm,
    bearing,
    screenBearing: (((bearing - map.getBearing()) % 360) + 360) % 360,
  };
}

/** "Take me there" stops at least this close: the atlas's own zoom for a point. */
const TAKE_ZOOM = 5.5;
/** …and close enough for the view to count as a region, with room to spare. */
const TAKE_SPAN_KM = REGIONAL_KM * 0.8;
const TAKE_MS = 900;

/**
 * Fly to a target so that the reader has arrived in place when the flight
 * ends: the target in the middle of where it counts as in view, and the view
 * no wider than a region whatever the window's size (on a large window the
 * atlas's usual zoom for a point still shows more than that).
 */
export function flyToTarget(map: QuestMap, insets: MapInsets | null, at: LngLat): void {
  const { clientWidth: width, clientHeight: height } = map.getContainer();
  if (!width || !height) return;
  const visible = visibleRect(width, height, insets) ?? whole(width, height);
  const zone = arrivalRect(visible, width);
  const diagonalPx = Math.hypot(visible.right - visible.left, visible.bottom - visible.top);
  map.flyTo({
    center: at,
    zoom: Math.max(map.getZoom(), TAKE_ZOOM, zoomForSpan(at[1], diagonalPx, TAKE_SPAN_KM)),
    padding: { top: zone.top, right: width - zone.right, bottom: height - zone.bottom, left: zone.left },
    duration: TAKE_MS,
  });
}
