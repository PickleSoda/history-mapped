/**
 * Era themes: the atlas restyles itself for the time and place on the map.
 * A small manifest (manifest.ts) says which era applies where and when; each
 * era's full theme is its own lazily loaded module (themes/*.ts), and its
 * fonts and textures load only when that era first becomes active.
 */

/** Procedural texture kinds (textures.ts draws them on a canvas). */
export type TextureKind =
  | 'dirt'
  | 'grain'
  | 'sand'
  | 'marble'
  | 'parchment'
  | 'linen'
  | 'halftone'
  | 'grid'
  | 'ripples'
  | 'tiles'
  | 'mosaic';

/** Repeating ornament bands (ornaments.ts draws them as SVG masks). */
export type OrnamentKind =
  | 'meander'
  | 'lotus'
  | 'dentil'
  | 'fluting'
  | 'knot'
  | 'arabesque'
  | 'zigzag'
  | 'wedges'
  | 'dots'
  | 'waves'
  | 'rivets'
  | 'stripes'
  | 'dashes'
  | 'filigree'
  | 'steps';

export interface EraTexture {
  kind: TextureKind;
  /** Ink colour of the texture's marks. */
  color: string;
  /** Strength over the UI surfaces (0..1). */
  ui: number;
  /** Strength over the map's land (0..1). */
  map: number;
}

export interface EraMapStyle {
  /** Country borders (OHM admin level 1-2). */
  border: string;
  /** Multiplies the basemap's border width. */
  borderWidth?: number;
  borderDash?: number[];
  borderBlur?: number;
  borderOpacity?: number;
  /** A wash over the land. */
  land?: { color: string; opacity: number };
  /** A wash over the sea. */
  sea?: { color: string; opacity: number };
}

export interface EraTheme {
  id: string;
  /** Light-mode palette; the dark palette is derived from it (tokens.ts). */
  paper: string;
  ink: string;
  accent: string;
  accent2?: string;
  /** Dark-mode background. Defaults to a deep shade of `ink`. */
  night?: string;
  /** Heading font: the CSS family plus the loader of its @fontsource files. */
  font?: { family: string; load: () => Promise<unknown> };
  texture?: EraTexture;
  /** The band under the top bar and above the timeline. */
  ornament?: OrnamentKind;
  /** A vertical band beside the side panels, such as a fluted column. */
  pillar?: OrnamentKind;
  map: EraMapStyle;
}

/** A lon/lat box: west, south, east, north. */
export type Box = [number, number, number, number];

/** One row of the manifest: where and when a theme applies. */
export interface EraEntry {
  id: string;
  label: string;
  /** The theme module this row loads (rows can share one). */
  theme: string;
  /** Inclusive years, BCE negative. */
  start: number;
  end: number;
  /** Absent for the global eras, which tile the whole timeline. */
  regions?: Box[];
  /** Among regional rows that match, the highest wins. */
  priority?: number;
  /** Two colours for previews before the theme module loads. */
  swatch: [string, string];
}
