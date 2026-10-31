/**
 * Map-story colours: a side's colour, its contingents' colours (their own, or
 * an automatic shade of the side's), and the lighter tint used for
 * conjectural arrows. Symbols are registered per colour (icons.ts), so
 * `storyPalette` lists every colour a story can draw with.
 */
import type { MapStoryDocument, StorySide, StoryUnit } from '@/lib/schemas/map-story';

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

/** Every colour the story draws symbols in (sides and contingents), deduplicated. */
export function storyPalette(doc: MapStoryDocument): string[] {
  const out = new Set<string>();
  for (const side of doc.sides) {
    out.add(side.color);
    for (const c of contingentColors(side).values()) out.add(c);
  }
  return [...out];
}
