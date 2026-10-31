/**
 * Core domain types for the Atlas frontend.
 *
 * These are the vocabulary the whole app speaks: the five entity groups, the
 * bounding box, the time state, and the derived `Scope` that every viewport
 * query keys on. See docs/architecture/frontend-app.md.
 */

/** The five entity groups. Lowercase tokens mirror the backend `EntityGroup` enum
 *  (POLITY, PLACE, EVENT, ECONOMY, CULTURE). */
export const ENTITY_GROUPS = [
  'polity',
  'place',
  'event',
  'economy',
  'culture',
] as const;

export type EntityGroup = (typeof ENTITY_GROUPS)[number];

/** Map viewport bounding box: west, south, east, north (degrees). */
export interface Bbox {
  w: number;
  s: number;
  e: number;
  n: number;
}

/** Timeline position — either a single instant or a window. Negative = BCE. */
export type TimeState =
  | { kind: 'instant'; year: number }
  | { kind: 'range'; start: number; end: number };

/** Share (0–1) of the map container hidden under floating UI on each side —
 *  the desktop panels, the mobile timeline and bottom sheet. */
export interface MapInsets {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

/**
 * The snapped query input: the URL plus the measured map insets (see
 * scope/snap.ts). All three boxes cover only the unobscured part of the map.
 */
export interface Scope {
  /** The visible area — what the "notable here" list ranks. */
  bbox: Bbox;
  /** `bbox` plus a ring of grid tiles — the map's sparse, prominent-only fetch,
   *  so just-off-screen pins are already loaded. */
  outer: Bbox;
  /** The middle of the visible area — fetched at a closer zoom's detail, so
   *  the map is densest where the user is looking. */
  core: Bbox;
  /** Integer tile-zoom level of the whole map (drives the impact threshold). */
  z: number;
  time: TimeState;
  /** Sorted for a stable query key regardless of toggle order. */
  groups: EntityGroup[];
}

/** Map projection mode (URL `view` param). */
export type ViewMode = 'map' | 'globe';

/** OpenHistoricalMap basemap style (URL `base` param). */
export type BasemapId = 'woodblock' | 'historical' | 'railway';
