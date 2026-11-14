/**
 * Small sRGB helpers for the era palettes: parse, mix and measure contrast.
 * Every value in and out is `#rrggbb`, which CSS, canvas and MapLibre all read.
 */

type Rgb = [number, number, number];

function parse(hex: string): Rgb {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) throw new Error(`not a #rrggbb colour: ${hex}`);
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function format([r, g, b]: Rgb): string {
  const h = (v: number) => Math.round(Math.min(255, Math.max(0, v))).toString(16).padStart(2, '0');
  return `#${h(r)}${h(g)}${h(b)}`;
}

/** `a` moved `amount` (0..1) of the way towards `b`. */
export function mix(a: string, b: string, amount: number): string {
  const [ar, ag, ab] = parse(a);
  const [br, bg, bb] = parse(b);
  const t = Math.min(1, Math.max(0, amount));
  return format([ar + (br - ar) * t, ag + (bg - ag) * t, ab + (bb - ab) * t]);
}

function channel(v: number): number {
  const s = v / 255;
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

/** WCAG relative luminance. */
export function luminance(hex: string): number {
  const [r, g, b] = parse(hex);
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

/** WCAG contrast ratio, 1..21. */
export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/**
 * `fg`, moved step by step towards `toward` until it reaches `min` contrast
 * against `bg` (or `toward` itself, if even that falls short).
 */
export function withContrast(fg: string, bg: string, min: number, toward: string): string {
  let out = fg;
  for (let t = 0.05; contrast(out, bg) < min && t <= 1.0001; t += 0.05) {
    out = mix(fg, toward, t);
  }
  return out;
}

/** `#rrggbb` as `rgba(r, g, b, a)`. */
export function rgba(hex: string, alpha: number): string {
  const [r, g, b] = parse(hex);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
