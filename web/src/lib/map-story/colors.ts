/**
 * Map-story colours: a side's colour, its contingents' colours (their own, or
 * an automatic shade of the side's), the neutral colour of a unit without a
 * side, and the fixed palette for routes, regions and places (mirrors the
 * API's, which precomputes ambient colours). Symbols are registered per
 * colour (icons.ts), so `storyPalette` lists every colour a story can draw with.
 */
import type { MapStoryDocument, StorySide, StoryUnit } from '@/lib/schemas/map-story';

/** What colours a feature: its kind and route/region kind, and its side. */
interface FeatureKind {
  kind: string;
  route_kind?: string | null;
  region_kind?: string | null;
  side?: string | null;
}

/** A unit, arrow or feature that belongs to no side, and anything unlisted below. */
export const NEUTRAL_COLOR = '#57534e';
/** A `disrupted` route. */
export const DISRUPTED_COLOR = '#dc2626';

// The API's palette (api/app/Support/MapStory): keep the two in step.
export const ROUTE_COLORS: Record<string, string> = {
  trade: '#b45309',
  voyage: '#0369a1',
  migration: '#7c3aed',
  pilgrimage: '#0f766e',
  campaign: '#b91c1c',
  road: '#57534e',
};
export const REGION_COLORS: Record<string, string> = {
  spread: '#7f1d1d',
  extent: '#1d4ed8',
  influence: '#a16207',
  affected: '#c2410c',
  front: '#be123c',
};
export const PLACE_COLORS: Record<string, string> = {
  outbreak: '#991b1b',
  port: '#0e7490',
  market: '#b45309',
  city: '#44403c',
};

/** A feature's palette colour, by its route kind, region kind or place kind. */
export function paletteColor(f: FeatureKind): string {
  if (f.kind === 'route') return ROUTE_COLORS[f.route_kind ?? ''] ?? NEUTRAL_COLOR;
  if (f.kind === 'region') return REGION_COLORS[f.region_kind ?? ''] ?? NEUTRAL_COLOR;
  return PLACE_COLORS[f.kind] ?? NEUTRAL_COLOR;
}

/** A feature's colour: its holder's at the step, else its own side's, else the palette's. */
export function featureColor(
  sides: Map<string, StorySide>,
  f: FeatureKind,
  heldBy?: string | null,
): string {
  return (heldBy && sides.get(heldBy)?.color) || (f.side && sides.get(f.side)?.color) || paletteColor(f);
}

function parse(hex: string): [number, number, number] | null {
  const m = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return null;
  const h = m[1].length === 3 ? [...m[1]].map((c) => c + c).join('') : m[1];
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)) as [number, number, number];
}

/** Mix a hex colour toward white (`amount` > 0) or black (< 0). Unparseable colours pass through. */
export function mix(hex: string, amount: number): string {
  const rgb = parse(hex);
  if (!rgb) return hex;
  const target = amount > 0 ? 255 : 0;
  const a = Math.min(1, Math.abs(amount));
  return `#${rgb.map((c) => Math.round(c + (target - c) * a).toString(16).padStart(2, '0')).join('')}`;
}

/**
 * The automatic shade for a side's `index`-th contingent: alternately lighter
 * and darker, further from the side's colour every other contingent.
 */
export function contingentShade(sideColor: string, index: number): string {
  const step = 0.24 + 0.16 * Math.floor(index / 2);
  return mix(sideColor, (index % 2 === 0 ? 1 : -1) * Math.min(step, 0.6));
}

/** contingent id → colour, for one side. */
export function contingentColors(side: StorySide): Map<string, string> {
  return new Map(side.contingents.map((c, i) => [c.id, c.color || contingentShade(side.color, i)]));
}

/** The colour a unit is drawn in: its contingent's, else its side's. */
export function unitColor(side: StorySide, unit: Pick<StoryUnit, 'contingent'>): string {
  return (unit.contingent && contingentColors(side).get(unit.contingent)) || side.color;
}

/** Every colour the story draws symbols in (sides, contingents, and the
 *  neutral colour when a unit or an arrow has no side), deduplicated. */
export function storyPalette(doc: MapStoryDocument): string[] {
  const out = new Set<string>();
  for (const side of doc.sides) {
    out.add(side.color);
    for (const c of contingentColors(side).values()) out.add(c);
  }
  const sideless =
    doc.units.some((u) => !u.side) ||
    doc.steps.some((s) => [s, ...s.beats].some((p) => p.moves.some((m) => !m.side && !m.unit)));
  if (sideless) out.add(NEUTRAL_COLOR);
  return [...out];
}

const ROUTE_LABELS: Record<string, string> = {
  trade: 'Trade route',
  voyage: 'Voyage',
  migration: 'Migration',
  pilgrimage: 'Pilgrimage',
  campaign: 'Campaign route',
  road: 'Road',
};
const REGION_LABELS: Record<string, string> = {
  spread: 'Spread',
  extent: 'Extent',
  influence: 'Influence',
  affected: 'Affected',
  front: 'Front',
};
const PLACE_LABELS: Record<string, string> = {
  city: 'City',
  port: 'Port',
  market: 'Market',
  mine: 'Mine',
  outbreak: 'Outbreak',
  site: 'Site',
};

/** What a feature is, in words: "Trade route", "Spread", "Outbreak"… */
export function featureKindLabel(f: FeatureKind): string {
  if (f.kind === 'route') return ROUTE_LABELS[f.route_kind ?? ''] ?? 'Route';
  if (f.kind === 'region') return REGION_LABELS[f.region_kind ?? ''] ?? 'Region';
  return PLACE_LABELS[f.kind] ?? f.kind.replace(/_/g, ' ');
}

/** One legend chip. */
export interface LegendEntry {
  swatch: string;
  label: string;
  style: 'fill' | 'line' | 'dot';
}

/**
 * The player's legend: the story's own `legend` entries, then one per route
 * kind, region kind and place kind it draws (and "Disrupted" when a route is),
 * skipping any the story already lists by label or by swatch and style.
 */
export function storyLegend(doc: MapStoryDocument): LegendEntry[] {
  const out: LegendEntry[] = doc.legend.map((l) => ({ swatch: l.swatch, label: l.label, style: l.style }));
  const seen = new Set(out.flatMap((l) => [`label:${l.label.toLowerCase()}`, `${l.style}:${l.swatch.toLowerCase()}`]));
  const add = (e: LegendEntry) => {
    const keys = [`label:${e.label.toLowerCase()}`, `${e.style}:${e.swatch.toLowerCase()}`];
    if (keys.some((k) => seen.has(k))) return;
    keys.forEach((k) => seen.add(k));
    out.push(e);
  };
  const sides = new Map(doc.sides.map((s) => [s.id, s]));
  for (const f of doc.features) {
    const style = f.kind === 'route' ? 'line' : f.kind === 'region' ? 'fill' : PLACE_LABELS[f.kind] ? 'dot' : null;
    if (style) add({ swatch: featureColor(sides, f), label: featureKindLabel(f), style });
  }
  const routes = new Set(doc.features.filter((f) => f.kind === 'route').map((f) => f.id));
  if (doc.steps.some((s) => Object.entries(s.features).some(([id, fs]) => routes.has(id) && fs?.state === 'disrupted'))) {
    add({ swatch: DISRUPTED_COLOR, label: 'Disrupted', style: 'line' });
  }
  return out;
}
