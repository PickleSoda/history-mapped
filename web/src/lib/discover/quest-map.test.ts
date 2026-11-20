import { describe, expect, it, vi } from 'vitest';
import type { MapInsets } from '@/types/atlas';
import { compassPoint, needsZoomIn, placeWarmth, REGIONAL_KM } from './quest';
import type { LngLat } from './quest';
import { arrivalRect, flyToTarget, readMapView, rectContains, visibleRect, zoomForSpan } from './quest-map';
import type { QuestMap } from './quest-map';

const HASTINGS: LngLat = [0.49, 50.91];
const MAGDALA: LngLat = [39.18, 11.35];
const NONE: MapInsets = { top: 0, right: 0, bottom: 0, left: 0 };

/**
 * A flat (web-mercator) map of `width` × `height` px with `center` in the
 * middle of its container, laid out as MapLibre does: the world is 512 px
 * wide at zoom 0 and repeats sideways.
 */
function flatMap({
  width = 1440,
  height = 800,
  center,
  zoom,
  bearing = 0,
}: {
  width?: number;
  height?: number;
  center: LngLat;
  zoom: number;
  bearing?: number;
}) {
  const world = 512 * 2 ** zoom;
  const x = (lng: number) => ((lng + 180) / 360) * world;
  const y = (lat: number) => (0.5 - Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360)) / (2 * Math.PI)) * world;
  const cx = x(center[0]);
  const cy = y(center[1]);
  const flyTo = vi.fn();
  const map: QuestMap = {
    getContainer: () => ({ clientWidth: width, clientHeight: height }),
    project: ([lng, lat]) => ({ x: x(lng) - cx + width / 2, y: y(lat) - cy + height / 2 }),
    unproject: ([px, py]) => ({
      lng: ((px - width / 2 + cx) / world) * 360 - 180,
      lat: (Math.atan(Math.exp((0.5 - (py - height / 2 + cy) / world) * 2 * Math.PI)) * 360) / Math.PI - 90,
    }),
    getBearing: () => bearing,
    getZoom: () => zoom,
    flyTo,
  };
  return { map, flyTo };
}

/** The camera centre that puts `at` on the pixel (px, py) of such a map. */
function centerPutting(at: LngLat, px: number, py: number, zoom: number, width = 1440, height = 800): LngLat {
  const { map } = flatMap({ width, height, center: at, zoom });
  const c = map.unproject([width - px, height - py]);
  return [c.lng, c.lat];
}

describe('the visible part of the map', () => {
  it('is the whole map with nothing over it', () => {
    expect(visibleRect(1440, 800, null)).toEqual({ left: 0, top: 0, right: 1440, bottom: 800 });
    expect(visibleRect(1440, 800, NONE)).toEqual({ left: 0, top: 0, right: 1440, bottom: 800 });
  });

  it('is what the panels leave', () => {
    expect(visibleRect(1440, 800, { left: 0.25, right: 0.25, top: 0.1, bottom: 0 })).toEqual({
      left: 360,
      top: 80,
      right: 1080,
      bottom: 800,
    });
  });

  it('is nothing under a sheet pulled right up', () => {
    expect(visibleRect(390, 760, { left: 0, right: 0, top: 0.1, bottom: 0.9 })).toBeNull();
    expect(visibleRect(390, 760, { left: 0.5, right: 0.5, top: 0, bottom: 0 })).toBeNull();
  });

  it('keeps a margin for the marker and the strip, when there is room for one', () => {
    expect(arrivalRect({ left: 360, top: 80, right: 1080, bottom: 800 }, 1440)).toEqual({
      left: 384,
      top: 144,
      right: 1056,
      bottom: 776,
    });
    // A map as narrow as a phone's: the strip is on two lines.
    expect(arrivalRect({ left: 0, top: 76, right: 390, bottom: 620 }, 390)).toEqual({
      left: 24,
      top: 176,
      right: 366,
      bottom: 596,
    });
    const slit = { left: 0, top: 80, right: 390, bottom: 180 };
    expect(arrivalRect(slit, 390)).toBe(slit);
  });

  it('holds its own edges', () => {
    const rect = { left: 10, top: 20, right: 30, bottom: 40 };
    expect(rectContains(rect, 10, 20)).toBe(true);
    expect(rectContains(rect, 30, 40)).toBe(true);
    expect(rectContains(rect, 9.9, 30)).toBe(false);
    expect(rectContains(rect, 20, 40.1)).toBe(false);
    expect(rectContains(rect, Number.NaN, 30)).toBe(false);
  });
});

describe('zoomForSpan', () => {
  it('is the zoom at which so many pixels span so many km', () => {
    expect(zoomForSpan(0, 512, 40_075.017)).toBeCloseTo(0);
    expect(zoomForSpan(0, 512, 40_075.017 / 8)).toBeCloseTo(3);
    expect(zoomForSpan(0, 1024, 40_075.017)).toBeCloseTo(1);
    // Half the km to a pixel at 60° north: the same span is one zoom further out.
    expect(zoomForSpan(60, 512, 40_075.017 / 8)).toBeCloseTo(2);
  });
});

describe('readMapView', () => {
  it('finds the target in the middle of a regional view', () => {
    const { map } = flatMap({ center: HASTINGS, zoom: 6 });
    const view = readMapView(map, NONE, HASTINGS);
    expect(view?.km).toBeLessThan(1);
    expect(view?.inView).toBe(true);
    // 1,647 px corner to corner at about 0.77 km a pixel.
    expect(view?.diagonalKm).toBeGreaterThan(1150);
    expect(view?.diagonalKm).toBeLessThan(1400);
    expect(view && placeWarmth(view)).toBe('here');
  });

  it('is only hot on a view of half the world, and says so', () => {
    const { map } = flatMap({ center: HASTINGS, zoom: 3 });
    const view = readMapView(map, NONE, HASTINGS);
    expect(view?.inView).toBe(true);
    expect(view?.diagonalKm).toBeGreaterThan(REGIONAL_KM);
    expect(view && placeWarmth(view)).toBe('hot');
    expect(view && needsZoomIn(view)).toBe(true);
  });

  it('never takes a view of the whole world, or of more than it, for a region', () => {
    for (const zoom of [0.4, 1, 1.5, 2]) {
      const { map } = flatMap({ center: [10, 20], zoom });
      expect(readMapView(map, NONE, HASTINGS)?.diagonalKm).toBeGreaterThan(REGIONAL_KM);
    }
  });

  it('measures from the middle of what the panels leave visible', () => {
    const { map } = flatMap({ center: HASTINGS, zoom: 6 });
    // A sidebar over the left quarter: the middle of the rest lies 180 px east of the target.
    const view = readMapView(map, { ...NONE, left: 0.25 }, HASTINGS);
    expect(view?.km).toBeGreaterThan(125);
    expect(view?.km).toBeLessThan(150);
    expect(view && compassPoint(view.bearing)).toBe('W');
    expect(view?.inView).toBe(true);
    expect(view && placeWarmth(view)).toBe('here');
  });

  it('does not count a target hidden under a panel', () => {
    const { map } = flatMap({ center: HASTINGS, zoom: 6 });
    const view = readMapView(map, { ...NONE, left: 0.6 }, HASTINGS);
    expect(view?.inView).toBe(false);
    expect(view && placeWarmth(view)).toBe('hot');
    expect(view && needsZoomIn(view)).toBe(false);
  });

  it('does not count a target under the strip or on the very edge', () => {
    const at = (px: number, py: number) =>
      readMapView(flatMap({ center: centerPutting(HASTINGS, px, py, 6), zoom: 6 }).map, NONE, HASTINGS)?.inView;
    expect(at(720, 30)).toBe(false);
    expect(at(720, 70)).toBe(true);
    expect(at(10, 400)).toBe(false);
    expect(at(30, 400)).toBe(true);
    expect(at(1430, 400)).toBe(false);
    expect(at(720, 790)).toBe(false);
    expect(at(720, 770)).toBe(true);
    expect(at(-200, 400)).toBe(false);
    // On a phone the strip takes two lines: more room is kept at the top.
    const onPhone = (px: number, py: number) =>
      readMapView(
        flatMap({ width: 390, height: 760, center: centerPutting(HASTINGS, px, py, 6, 390, 760), zoom: 6 }).map,
        NONE,
        HASTINGS,
      )?.inView;
    expect(onPhone(195, 80)).toBe(false);
    expect(onPhone(195, 110)).toBe(true);
  });

  it('sees a target on the next copy of the world, across the date line', () => {
    const { map } = flatMap({ center: [179, 0], zoom: 6 });
    const view = readMapView(map, NONE, [-179.5, 0]);
    expect(view?.inView).toBe(true);
    expect(view?.km).toBeGreaterThan(160);
    expect(view?.km).toBeLessThan(172);
    expect(view && compassPoint(view.bearing)).toBe('E');
    const west = readMapView(flatMap({ center: [-179, 0], zoom: 6 }).map, NONE, [179.5, 0]);
    expect(west?.inView).toBe(true);
    expect(west && compassPoint(west.bearing)).toBe('W');
  });

  it('does not count the far side of the globe, which projects onto the screen all the same', () => {
    const { map } = flatMap({ center: HASTINGS, zoom: 6 });
    const globe: QuestMap = { ...map, project: () => ({ x: 720, y: 400 }) };
    const antipode: LngLat = [HASTINGS[0] - 180, -HASTINGS[1]];
    const view = readMapView(globe, NONE, antipode);
    expect(view?.km).toBeGreaterThan(19_000);
    expect(view?.inView).toBe(false);
    expect(view && placeWarmth(view)).toBe('cold');
  });

  it('still measures on a map that is covered whole, where nothing is in view', () => {
    const { map } = flatMap({ center: HASTINGS, zoom: 6 });
    const view = readMapView(map, { top: 0.1, right: 0, bottom: 0.9, left: 0 }, HASTINGS);
    expect(view?.km).toBeLessThan(1);
    expect(view?.inView).toBe(false);
    expect(view && placeWarmth(view)).toBe('hot');
  });

  it('gives the way on screen when the map is turned', () => {
    // 600 px above the middle of the screen on a map turned a quarter: the fake map does not turn its pixels, only its bearing.
    const north: LngLat = [HASTINGS[0], 56];
    const upright = readMapView(flatMap({ center: HASTINGS, zoom: 6 }).map, NONE, north);
    const turned = readMapView(flatMap({ center: HASTINGS, zoom: 6, bearing: 90 }).map, NONE, north);
    expect(upright?.bearing).toBeCloseTo(0);
    expect(upright?.screenBearing).toBeCloseTo(0);
    expect(turned?.bearing).toBeCloseTo(0);
    expect(turned?.screenBearing).toBeCloseTo(270);
  });

  it('has nothing to say about a map with no size', () => {
    expect(readMapView(flatMap({ width: 0, height: 0, center: HASTINGS, zoom: 6 }).map, NONE, HASTINGS)).toBeNull();
  });
});

describe('flyToTarget', () => {
  it('flies to the atlas’s zoom for a point when that already shows no more than a region', () => {
    const { map, flyTo } = flatMap({ center: [10, 20], zoom: 3 });
    flyToTarget(map, NONE, HASTINGS);
    expect(flyTo).toHaveBeenCalledWith({
      center: HASTINGS,
      zoom: 5.5,
      padding: { top: 64, right: 24, bottom: 24, left: 24 },
      duration: 900,
    });
  });

  it('goes closer on a large window near the equator, where that zoom shows more than a region', () => {
    const { map, flyTo } = flatMap({ width: 2560, height: 1300, center: [10, 20], zoom: 3 });
    flyToTarget(map, NONE, MAGDALA);
    const { zoom } = flyTo.mock.calls[0][0];
    expect(zoom).toBeGreaterThan(6.4);
    expect(zoom).toBeLessThan(6.7);
  });

  it('never zooms out of a closer view', () => {
    const { map, flyTo } = flatMap({ center: [10, 20], zoom: 9 });
    flyToTarget(map, NONE, HASTINGS);
    expect(flyTo.mock.calls[0][0].zoom).toBe(9);
  });

  it('pads the flight by the panels, so the target lands where it counts as in view', () => {
    const { map, flyTo } = flatMap({ center: [10, 20], zoom: 3 });
    flyToTarget(map, { left: 0.25, right: 0.25, top: 0.1, bottom: 0 }, HASTINGS);
    expect(flyTo.mock.calls[0][0].padding).toEqual({ top: 144, right: 384, bottom: 24, left: 384 });
    // Covered whole: fly on the map as it is.
    flyTo.mockClear();
    flyToTarget(map, { left: 0, right: 0, top: 0.1, bottom: 0.9 }, HASTINGS);
    expect(flyTo.mock.calls[0][0].padding).toEqual({ top: 64, right: 24, bottom: 24, left: 24 });
  });

  it('does nothing on a map with no size', () => {
    const { map, flyTo } = flatMap({ width: 0, height: 0, center: [10, 20], zoom: 3 });
    flyToTarget(map, NONE, HASTINGS);
    expect(flyTo).not.toHaveBeenCalled();
  });

  it.each([
    ['a laptop', 1440, 800, { ...NONE, left: 0.24 }, HASTINGS],
    ['a laptop with both panels open', 1280, 720, { ...NONE, left: 0.26, right: 0.3 }, MAGDALA],
    ['a large window at the equator', 2560, 1300, { ...NONE, left: 0.14 }, [102.3, 0.5] as LngLat],
    ['a large window in the far north', 2560, 1300, NONE, [-21.9, 64.1] as LngLat],
    ['a large window in the south', 1920, 960, { ...NONE, left: 0.18 }, [-70.74, -34.17] as LngLat],
    ['a phone with the sheet half up', 390, 760, { top: 0.1, right: 0, bottom: 0.56, left: 0 }, MAGDALA],
    ['a phone with the sheet down', 390, 760, { top: 0.1, right: 0, bottom: 0.18, left: 0 }, HASTINGS],
  ] as const)('ends with the reader there in place: %s', (_what, width, height, insets, at) => {
    const from = flatMap({ width, height, center: [60, 30], zoom: 2.5 });
    flyToTarget(from.map, insets, [...at]);
    const { center, zoom, padding } = from.flyTo.mock.calls[0][0];
    // Where the flight ends: `center` in the middle of the padded view, at `zoom`.
    const px = padding.left + (width - padding.left - padding.right) / 2;
    const py = padding.top + (height - padding.top - padding.bottom) / 2;
    const landed = flatMap({ width, height, center: centerPutting(center, px, py, zoom, width, height), zoom });
    const view = readMapView(landed.map, insets, [...at]);
    expect(view?.inView).toBe(true);
    expect(view?.diagonalKm).toBeLessThan(REGIONAL_KM);
    expect(view && placeWarmth(view)).toBe('here');
  });
});
