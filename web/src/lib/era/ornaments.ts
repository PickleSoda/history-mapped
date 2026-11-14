import type { OrnamentKind } from '@/lib/era/types';

/**
 * Each era's ornament as pixel art for the thin border down the side panels'
 * inner edges: rows of `#` (ink) and `.` (paper), BORDER_WIDTH pixels wide,
 * repeated downwards. Column 0 sits against the panel. The tiles are drawn at
 * their real size from whole pixels, so the border stays crisp and solid (a
 * scaled-down drawing blurs into half-transparent pixels at this width). They
 * are CSS mask images: the ink colour comes from the theme (`--era-ornament`).
 */
export const BORDER_WIDTH = 6;

const TILES: Record<OrnamentKind, string[]> = {
  // A Greek key running down between two rules.
  meander: ['######', '#....#', '####.#', '#..#.#', '#.##.#', '#....#', '#.####', '#.#..#', '#.#.##', '#....#'],
  // Lotus buds on a stem, between two rules.
  lotus: ['#....#', '#.##.#', '######', '######', '#.##.#', '#.##.#', '#....#'],
  // A cornice: a fillet against the panel and a row of dentil blocks.
  dentil: ['#.....', '#.####', '#.####', '#.####', '#.....'],
  // Column flutes.
  fluting: ['#.##.#'],
  // A braid of two crossing strands.
  knot: ['#....#', '.#..#.', '..##..', '..##..', '.#..#.', '#....#'],
  // Interlocking lozenges between two rules.
  arabesque: ['#.##.#', '##..##', '#.##.#', '#....#'],
  zigzag: ['##....', '.##...', '..##..', '...##.', '....##', '...##.', '..##..', '.##...'],
  // Cuneiform wedges, pointing alternately left and right.
  wedges: ['####.#', '#.#..#', '#.#..#', '#....#', '#.####', '#..#.#', '#..#.#', '#....#'],
  // Beads between two rules.
  dots: ['#....#', '#.##.#', '#.##.#', '#....#'],
  // A running wave.
  waves: ['..##..', '.#....', '#.....', '#.....', '.#....', '..##..', '....#.', '.....#', '.....#', '....#.'],
  // A riveted steel strap.
  rivets: ['#.##.#', '######', '######', '#.##.#', '#....#', '#....#'],
  // Hazard stripes.
  stripes: ['###...', '.###..', '..###.', '...###', '#...##', '##...#'],
  // A dashed line between two rules.
  dashes: ['#.##.#', '#.##.#', '#.##.#', '#....#', '#....#'],
  // A Victorian rope moulding.
  filigree: ['###..#', '#.##.#', '#..###', '##..##'],
  // A Mesoamerican stepped fret.
  steps: ['#.....', '##....', '###...', '####..', '#####.', '######'],
};

export const ORNAMENT_KINDS = Object.keys(TILES) as OrnamentKind[];

/** The rows of `kind`'s tile (for tests and previews). */
export function borderTile(kind: OrnamentKind): readonly string[] {
  return TILES[kind];
}

/** `kind`'s tile as an SVG data URI, one unit per CSS pixel. */
export function borderUrl(kind: OrnamentKind): string {
  const rows = TILES[kind];
  const rects = rows.flatMap((row, y) =>
    [...row.matchAll(/#+/g)].map((m) => `<rect x="${m.index}" y="${y}" width="${m[0].length}" height="1"/>`),
  );
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${BORDER_WIDTH}" height="${rows.length}" ` +
    `viewBox="0 0 ${BORDER_WIDTH} ${rows.length}" shape-rendering="crispEdges">${rects.join('')}</svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}
