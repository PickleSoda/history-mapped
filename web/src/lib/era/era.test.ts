import { describe, expect, it } from 'vitest';
import { contrast, mix, withContrast } from '@/lib/era/color';
import { THEME_IDS } from '@/lib/era/loader';
import { ERA_ENTRIES, GLOBAL_ERAS, REGIONAL_MAX_SPAN } from '@/lib/era/manifest';
import {
  applyEraToMap,
  borderPaint,
  borderRole,
  ERA_LAND_LAYER,
  ERA_SEA_LAYER,
  PATTERNED_WIDTH,
  scaleWidth,
} from '@/lib/era/map-style';
import { ORNAMENT_KINDS, ornamentUrl, pillarUrl } from '@/lib/era/ornaments';
import { globalEra, resolveEra } from '@/lib/era/resolve';
import { textureAlpha } from '@/lib/era/textures';
import { eraTokens, MUTED_CONTRAST, TEXT_CONTRAST, themeCss } from '@/lib/era/tokens';
import type { EraTheme, TextureKind } from '@/lib/era/types';
import type { Bbox } from '@/types/atlas';

const themes = Object.values(
  import.meta.glob<{ default: EraTheme }>('./themes/*.ts', { eager: true }),
).map((m) => m.default);

const HEX = /^#[0-9a-f]{6}$/i;

/** A view `span` degrees wide centred on lng/lat. */
function view(lng: number, lat: number, span = 12): Bbox {
  return { w: lng - span / 2, e: lng + span / 2, s: lat - span / 3, n: lat + span / 3 };
}

describe('era manifest', () => {
  it('tiles the whole timeline with global eras, in order and without gaps', () => {
    for (let i = 1; i < GLOBAL_ERAS.length; i++) {
      expect(GLOBAL_ERAS[i].start).toBe(GLOBAL_ERAS[i - 1].end + 1);
    }
    expect(globalEra(-200000).id).toBe('prehistory');
    expect(globalEra(-3000).id).toBe('bronze-age');
    expect(globalEra(1945).id).toBe('world-wars');
    expect(globalEra(1946).id).toBe('cold-war');
    expect(globalEra(2024).id).toBe('global-age');
    expect(globalEra(500000).id).toBe('global-age');
  });

  it('has unique ids and points every row at a theme module', () => {
    const ids = ERA_ENTRIES.map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const entry of ERA_ENTRIES) {
      expect(THEME_IDS).toContain(entry.theme);
      expect(entry.start).toBeLessThanOrEqual(entry.end);
      expect(entry.swatch.every((c) => HEX.test(c))).toBe(true);
    }
  });
});

describe('resolveEra', () => {
  it('uses the global era when the view is wide', () => {
    const wide: Bbox = { w: -25, e: 65, s: 15, n: 60 };
    expect(wide.e - wide.w).toBeGreaterThan(REGIONAL_MAX_SPAN);
    expect(resolveEra(-1300, wide).id).toBe('bronze-age');
    expect(resolveEra(-1300, null).id).toBe('bronze-age');
  });

  it.each([
    [-1300, 31.2, 26, 'egypt'],
    [-2000, 44.4, 32.5, 'mesopotamia'],
    [-400, 23.7, 38, 'greece'],
    [-100, 23.7, 38, 'roman-world'],
    [100, 12.5, 41.9, 'rome'],
    [100, 2.3, 46, 'roman-world'],
    [100, 31.2, 26, 'roman-world'],
    [900, 44.4, 33.3, 'islamic-golden-age'],
    [900, 29, 41, 'byzantium'],
    [900, 10.7, 59.9, 'viking-age'],
    [1400, -99.1, 19.4, 'mexica'],
    [1700, 139.7, 35.7, 'edo-japan'],
    [1700, 116.4, 39.9, 'imperial-china'],
    [1850, -0.1, 51.5, 'victorian'],
    [1950, -0.1, 51.5, 'cold-war'],
    [1300, 2.3, 48.9, 'medieval'],
  ])('year %i at %f,%f is %s', (year, lng, lat, id) => {
    expect(resolveEra(year, view(lng, lat)).id).toBe(id);
  });
});

describe('colour helpers', () => {
  it('mixes and measures contrast', () => {
    expect(mix('#000000', '#ffffff', 0.5)).toBe('#808080');
    expect(contrast('#000000', '#ffffff')).toBeCloseTo(21, 5);
    const pushed = withContrast('#999999', '#ffffff', 4.5, '#000000');
    expect(contrast(pushed, '#ffffff')).toBeGreaterThanOrEqual(4.5);
  });
});

describe('era themes', () => {
  it('has one module per id, named after it', () => {
    expect(themes.map((t) => t.id).sort()).toEqual([...THEME_IDS].sort());
  });

  it.each(themes.map((t) => [t.id, t] as const))('%s has valid colours and map styling', (_, theme) => {
    for (const c of [theme.paper, theme.ink, theme.accent, theme.accent2, theme.night].filter(Boolean)) {
      expect(c).toMatch(HEX);
    }
    expect(theme.map.border).toMatch(HEX);
    if (theme.texture) {
      expect(theme.texture.color).toMatch(HEX);
      expect(theme.texture.ui).toBeGreaterThan(0);
      expect(theme.texture.ui).toBeLessThanOrEqual(1);
    }
  });

  it.each(themes.flatMap((t) => (['light', 'dark'] as const).map((mode) => [t.id, mode, t] as const)))(
    '%s (%s) keeps text readable',
    (_, mode, theme) => {
      const t = eraTokens(theme, mode);
      for (const value of Object.values(t)) expect(value).toMatch(HEX);
      expect(contrast(t['--foreground'], t['--background'])).toBeGreaterThanOrEqual(TEXT_CONTRAST);
      expect(contrast(t['--card-foreground'], t['--card'])).toBeGreaterThanOrEqual(TEXT_CONTRAST - 0.5);
      expect(contrast(t['--muted-foreground'], t['--muted'])).toBeGreaterThanOrEqual(MUTED_CONTRAST);
      expect(contrast(t['--muted-foreground'], t['--background'])).toBeGreaterThanOrEqual(4.5);
      expect(contrast(t['--primary-foreground'], t['--primary'])).toBeGreaterThanOrEqual(4.5);
    },
  );

  it('writes a light and a dark block, with the heading font', () => {
    const rome = themes.find((t) => t.id === 'rome')!;
    const css = themeCss(rome, 'data:x', 'data:y');
    expect(css).toContain('html[data-era-theme="rome"] {');
    expect(css).toContain('html.dark[data-era-theme="rome"] {');
    expect(css).toContain("--era-font-heading: 'Cinzel Variable'");
    expect(css).toContain('--era-ornament-image: url("data:x");');
    expect(css).toContain('--era-pillar-image: url("data:y");');
  });
});

describe('ornaments', () => {
  it.each(ORNAMENT_KINDS)('%s draws a horizontal and a vertical tile', (kind) => {
    const h = decodeURIComponent(ornamentUrl(kind));
    expect(h).toMatch(/^data:image\/svg\+xml,<svg [^>]*height="12"/);
    const v = decodeURIComponent(pillarUrl(kind));
    expect(v).toMatch(kind === 'fluting' ? /height="12"/ : /width="12"/);
  });
});

describe('textures', () => {
  const kinds: TextureKind[] = ['dirt', 'grain', 'sand', 'marble', 'parchment', 'linen', 'halftone', 'grid', 'ripples', 'tiles', 'mosaic'];
  it.each(kinds)('%s is deterministic and leaves marks', (kind) => {
    const a = textureAlpha(kind, 128);
    expect(a).toHaveLength(128 * 128);
    expect(Array.from(a).some((v) => v > 0)).toBe(true);
    expect(Array.from(a).some((v) => v === 0 || v < 40)).toBe(true);
    expect(textureAlpha(kind, 128)).toEqual(a);
  });
});

describe('map styling', () => {
  it('scales line widths without breaking zoom expressions', () => {
    expect(scaleWidth(2, 1.5)).toBe(3);
    expect(scaleWidth(['interpolate', ['linear'], ['zoom'], 0, 4, 8, 6], 0.5)).toEqual([
      'interpolate', ['linear'], ['zoom'], 0, 2, 8, 3,
    ]);
    expect(scaleWidth(['step', ['zoom'], 1, 5, 2], 2)).toEqual(['step', ['zoom'], 2, 5, 4]);
    expect(scaleWidth({ stops: [[0, 1], [10, 3]] }, 2)).toEqual({ stops: [[0, 2], [10, 6]] });
    expect(scaleWidth(['get', 'w'], 2)).toEqual(['get', 'w']);
  });

  it('classifies OHM boundary layers', () => {
    const line = (id: string, filter: unknown) =>
      ({ id, type: 'line', source: 'ohm', 'source-layer': 'land_ohm_lines', filter }) as never;
    const country = ['all', ['in', ['get', 'admin_level'], ['literal', [1, 2]]], ['==', ['get', 'type'], 'administrative']];
    expect(borderRole(line('admin_countrylines_z10', country))).toBe('country');
    expect(borderRole(line('admin_country_lines_z10_case', country))).toBe('case');
    expect(borderRole(line('state_lines_admin_4', ['==', ['get', 'admin_level'], 4]))).toBe('other');
    expect(borderRole({ id: 'water', type: 'fill', 'source-layer': 'water_areas' } as never)).toBeNull();
  });

  /** Just enough of a MapLibre map for applyEraToMap. */
  function fakeMap() {
    const layers: Array<Record<string, unknown> & { id: string }> = [
      { id: 'background', type: 'background', paint: { 'background-color': '#cfb37d' } },
      { id: 'land', type: 'fill', source: 'osm_land', 'source-layer': 'land', paint: { 'fill-color': '#ece1cb' } },
      { id: 'water_areas', type: 'fill', source: 'ohm', 'source-layer': 'water_areas', paint: {} },
      {
        id: 'admin_countrylines_z10',
        type: 'line',
        source: 'ohm',
        'source-layer': 'land_ohm_lines',
        filter: ['in', ['get', 'admin_level'], ['literal', [1, 2]]],
        paint: { 'line-color': '#9da9ae', 'line-width': 4, 'line-pattern': 'woodblock-splotching-light' },
      },
    ];
    const paint = new Map(layers.map((l) => [l.id, { ...(l.paint as object) } as Record<string, unknown>]));
    const images = new Set<string>();
    const map = {
      style: {},
      getStyle: () => ({ layers: layers.map((l) => ({ ...l, paint: paint.get(l.id) })) }),
      getLayer: (id: string) => layers.find((l) => l.id === id),
      getPaintProperty: (id: string, p: string) => paint.get(id)?.[p],
      setPaintProperty: (id: string, p: string, v: unknown) => {
        const props = paint.get(id)!;
        if (v === undefined) delete props[p];
        else props[p] = v;
      },
      addLayer: (layer: { id: string; paint?: object }, before?: string) => {
        const at = before ? layers.findIndex((l) => l.id === before) : layers.length;
        layers.splice(at < 0 ? layers.length : at, 0, layer as never);
        paint.set(layer.id, { ...(layer.paint ?? {}) });
      },
      removeLayer: (id: string) => {
        layers.splice(layers.findIndex((l) => l.id === id), 1);
        paint.delete(id);
      },
      hasImage: (id: string) => images.has(id),
      addImage: (id: string) => images.add(id),
      removeImage: (id: string) => images.delete(id),
    };
    return { map: map as never, layers, paint };
  }

  const rome = () => themes.find((t) => t.id === 'rome')!;
  const egypt = () => themes.find((t) => t.id === 'egypt')!;

  it('restyles borders, adds the washes in place, and restores everything', () => {
    const { map, layers, paint } = fakeMap();
    applyEraToMap(map, rome());

    const border = paint.get('admin_countrylines_z10')!;
    expect(border['line-color']).toBe(rome().map.border);
    expect(border['line-pattern']).toBeUndefined();
    // The basemap drew it with a pattern, so the solid line is thinner.
    expect(border['line-width']).toBeCloseTo(4 * PATTERNED_WIDTH * (rome().map.borderWidth ?? 1));
    expect(layers.map((l) => l.id)).toEqual([
      'background', ERA_SEA_LAYER, 'land', ERA_LAND_LAYER, 'water_areas', 'admin_countrylines_z10',
    ]);
    expect(paint.get(ERA_LAND_LAYER)!['fill-color']).toBe(rome().map.land!.color);

    applyEraToMap(map, null);
    expect(paint.get('admin_countrylines_z10')).toEqual({
      'line-color': '#9da9ae', 'line-width': 4, 'line-pattern': 'woodblock-splotching-light',
    });
    expect(layers.map((l) => l.id)).toEqual(['background', 'land', 'water_areas', 'admin_countrylines_z10']);
  });

  it('never compounds one era on another', () => {
    const { map, paint } = fakeMap();
    applyEraToMap(map, rome());
    applyEraToMap(map, egypt());
    applyEraToMap(map, egypt());
    const border = paint.get('admin_countrylines_z10')!;
    expect(border['line-color']).toBe(egypt().map.border);
    expect(border['line-width']).toBeCloseTo(4 * PATTERNED_WIDTH * (egypt().map.borderWidth ?? 1));
    expect(border['line-dasharray']).toEqual(egypt().map.borderDash);
  });

  it('gives case and state lines a lighter era colour', () => {
    const current = () => undefined;
    expect(borderPaint('case', current, rome())['line-color']).toBe(mix(rome().map.border, rome().paper, 0.72));
    expect(borderPaint('other', current, rome())['line-color']).toBe(mix(rome().map.border, rome().paper, 0.35));
  });
});
