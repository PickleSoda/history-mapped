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

/** The snapped query input. Pure function of the URL (see scope/snap.ts). */
export interface Scope {
  bbox: Bbox;
  /** Integer tile-zoom level the bbox was snapped to. */
  z: number;
  time: TimeState;
  /** Sorted for a stable query key regardless of toggle order. */
  groups: EntityGroup[];
}

/** Map projection mode (URL `view` param). */
export type ViewMode = 'map' | 'globe';
