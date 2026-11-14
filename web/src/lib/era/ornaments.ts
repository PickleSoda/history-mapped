import type { OrnamentKind } from '@/lib/era/types';

/**
 * Repeating ornament bands as SVG tiles, 12 units tall. They are used as CSS
 * mask images, so only their shape matters: the band's colour comes from the
 * theme (`--era-ornament`) and follows light and dark mode.
 */
const H = 12;

const S = 'fill="none" stroke="#000" stroke-width="1.5" stroke-linecap="square"';
const F = 'fill="#000"';

const TILES: Record<OrnamentKind, { w: number; body: string }> = {
  // Greek key: a baseline with a squared spiral on each unit.
  meander: { w: 12, body: `<path ${S} d="M0 10.5H12M3 10.5V1.5H10.5V7.5H6V4.5H8"/>` },
  // A lotus bud between two dots, on a ground line.
  lotus: {
    w: 16,
    body: `<path ${F} d="M8 1C11 4.5 11 8.5 8 10.5C5 8.5 5 4.5 8 1Z"/><circle ${F} cx="0" cy="8" r="1.3"/><circle ${F} cx="16" cy="8" r="1.3"/><rect ${F} x="0" y="11" width="16" height="1"/>`,
  },
  // A cornice: a top fillet over a row of dentil blocks.
  dentil: { w: 10, body: `<rect ${F} x="0" y="0" width="10" height="1.4"/><rect ${F} x="1.5" y="3" width="6" height="9"/>` },
  // Column flutes: parallel vertical channels.
  fluting: { w: 5, body: `<rect ${F} x="1.5" y="0" width="1.6" height="12"/>` },
  // Two interlaced strands.
  knot: {
    w: 16,
    body: `<path ${S} d="M0 6C4 0 4 0 8 6S12 12 16 6"/><path ${S} d="M0 6C4 12 4 12 8 6S12 0 16 6"/>`,
  },
  // Eight-pointed stars.
  arabesque: {
    w: 14,
    body: `<rect ${F} x="4" y="3" width="6" height="6"/><rect ${F} x="4" y="3" width="6" height="6" transform="rotate(45 7 6)"/><circle ${F} cx="0" cy="6" r="1"/><circle ${F} cx="14" cy="6" r="1"/>`,
  },
  zigzag: { w: 8, body: `<path ${S} d="M0 10L4 2L8 10"/>` },
  // Cuneiform: a vertical and a horizontal wedge.
  wedges: {
    w: 12,
    body: `<path ${F} d="M1 2H5.5L3.25 5Z"/><rect ${F} x="2.6" y="4.5" width="1.3" height="6"/><path ${F} d="M6.5 6.5V11L9.5 8.75Z"/><rect ${F} x="9" y="8.1" width="3" height="1.3"/>`,
  },
  dots: { w: 8, body: `<circle ${F} cx="4" cy="6" r="1.7"/>` },
  // Scalloped waves.
  waves: {
    w: 12,
    body: `<path fill="none" stroke="#000" stroke-width="1.2" d="M0 12A6 6 0 0 1 12 12M3 12A3 3 0 0 1 9 12"/>`,
  },
  rivets: { w: 14, body: `<rect ${F} x="0" y="5.4" width="14" height="1.2"/><circle ${F} cx="7" cy="6" r="2.4"/>` },
  stripes: { w: 8, body: `<path ${F} d="M0 12L4 0H8L4 12Z"/>` },
  dashes: { w: 10, body: `<rect ${F} x="0" y="5" width="6" height="2"/>` },
  // Victorian scrolls.
  filigree: {
    w: 20,
    body: `<path fill="none" stroke="#000" stroke-width="1.2" d="M0 6C3 0 8 0 8 4C8 7 4.5 7 4.5 5M20 6C17 12 12 12 12 8C12 5 15.5 5 15.5 7M8 4C10 6 10 6 12 8"/>`,
  },
  // A Mesoamerican stepped fret.
  steps: { w: 16, body: `<path ${S} d="M0 10.5H4V7H8V3.5H12V1.5H15V7H12.5"/>` },
};

function encode(svg: string): string {
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

/** A horizontal band tile for `kind`, as a data URI. */
export function ornamentUrl(kind: OrnamentKind): string {
  const { w, body } = TILES[kind];
  return encode(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${H}" viewBox="0 0 ${w} ${H}">${body}</svg>`);
}

/**
 * A vertical band tile (for the pillars beside the panels): the horizontal
 * tile turned a quarter, except flutes, which already run vertically.
 */
export function pillarUrl(kind: OrnamentKind): string {
  if (kind === 'fluting') return ornamentUrl(kind);
  const { w, body } = TILES[kind];
  return encode(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${H}" height="${w}" viewBox="0 0 ${H} ${w}"><g transform="translate(${H} 0) rotate(90)">${body}</g></svg>`,
  );
}

export const ORNAMENT_KINDS = Object.keys(TILES) as OrnamentKind[];
