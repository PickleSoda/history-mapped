import { describe, expect, it } from 'vitest';
import { geometriesBounds, isPointBounds } from './map-focus';

const point = (lng: number, lat: number) => ({ type: 'Point', coordinates: [lng, lat] });

describe('geometriesBounds', () => {
  it('returns a collapsed box for a single point', () => {
    const b = geometriesBounds([point(10, 20)]);
    expect(b).toEqual([
      [10, 20],
      [10, 20],
    ]);
    expect(isPointBounds(b!)).toBe(true);
  });

  it('frames a polygon by its min/max coordinates', () => {
    const poly = {
      type: 'Polygon',
      coordinates: [
        [
          [0, 0],
          [4, 1],
          [2, 5],
          [0, 0],
        ],
      ],
    };
    const b = geometriesBounds([poly]);
    expect(b).toEqual([
      [0, 0],
      [4, 5],
    ]);
    expect(isPointBounds(b!)).toBe(false);
  });

  it('unions multiple geometries, ignoring nulls', () => {
    const b = geometriesBounds([point(-5, 2), null, point(8, -3), undefined]);
    expect(b).toEqual([
      [-5, -3],
      [8, 2],
    ]);
  });

  it('unwraps Feature and GeometryCollection wrappers', () => {
    const feature = { type: 'Feature', geometry: point(1, 1), properties: {} };
    const collection = {
      type: 'GeometryCollection',
      geometries: [point(-2, -2), point(3, 4)],
    };
    expect(geometriesBounds([feature, collection])).toEqual([
      [-2, -2],
      [3, 4],
    ]);
  });

  it('returns null when nothing carries a coordinate', () => {
    expect(geometriesBounds([])).toBeNull();
    expect(geometriesBounds([null, undefined, {}, { type: 'Point' }])).toBeNull();
  });
});
