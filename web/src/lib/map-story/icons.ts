/**
 * Battle-map symbols, drawn on a canvas and registered as map images.
 *
 * The glyph language follows military map convention loosely: foot are a
 * cross (X), horse a single diagonal, missile troops their weapon, artillery a
 * dot; heavier troops get a frame. Glyphs are white with a dark halo so they
 * read on any side colour. Pins (commander, camp, baggage), arrowheads and
 * note markers are coloured per side, so their image ids carry the colour.
 */
import type { Map as MapLibreMap } from 'maplibre-gl';

const SIZE = 32;
const RATIO = 2;

type Draw = (c: CanvasRenderingContext2D) => void;

const line = (c: CanvasRenderingContext2D, ...pts: number[]) => {
  c.moveTo(pts[0], pts[1]);
  for (let i = 2; i < pts.length; i += 2) c.lineTo(pts[i], pts[i + 1]);
};
const frame: Draw = (c) => c.rect(5, 7, 22, 18);
const cross: Draw = (c) => {
  line(c, 8, 9, 24, 23);
  line(c, 24, 9, 8, 23);
};
const slash: Draw = (c) => line(c, 8, 23, 24, 9);
const bow: Draw = (c) => {
  c.moveTo(11, 6);
  c.quadraticCurveTo(25, 16, 11, 26);
  line(c, 11, 6, 11, 26);
  line(c, 7, 16, 24, 16);
  line(c, 20, 12, 24, 16, 20, 20);
};
const wheel: Draw = (c) => {
  c.moveTo(25, 16);
  c.arc(16, 16, 9, 0, Math.PI * 2);
  line(c, 16, 7, 16, 25);
  line(c, 7, 16, 25, 16);
};

/** Glyph per unit kind; anything unknown draws as generic foot. */
const GLYPHS: Record<string, Draw> = {
  infantry: cross,
  heavy_infantry: (c) => {
    frame(c);
    cross(c);
  },
  light_infantry: (c) => {
    line(c, 11, 12, 21, 20);
    line(c, 21, 12, 11, 20);
  },
  pikemen: (c) => {
    cross(c);
    line(c, 16, 3, 16, 29);
  },
  archers: bow,
  slingers: (c) => {
    c.moveTo(22, 21);
    c.arc(18, 21, 4, 0, Math.PI * 2);
    c.moveTo(14, 21);
    c.quadraticCurveTo(8, 8, 18, 6);
  },
  crossbowmen: (c) => {
    c.moveTo(6, 13);
    c.quadraticCurveTo(16, 4, 26, 13);
    line(c, 16, 8, 16, 27);
    line(c, 6, 13, 26, 13);
  },
  musketeers: (c) => {
    cross(c);
    c.moveTo(19, 16);
    c.arc(16, 16, 3, 0, Math.PI * 2);
  },
  cavalry: slash,
  heavy_cavalry: (c) => {
    frame(c);
    slash(c);
  },
  light_cavalry: (c) => line(c, 11, 21, 21, 11),
  horse_archers: (c) => {
    slash(c);
    c.moveTo(9, 9);
    c.quadraticCurveTo(15, 11, 13, 17);
  },
  chariots: wheel,
  elephants: (c) => {
    c.moveTo(24, 14);
    c.arc(17, 14, 7, 0, Math.PI * 2);
    c.moveTo(10, 15);
    c.quadraticCurveTo(6, 22, 10, 26);
    line(c, 14, 20, 14, 26);
    line(c, 21, 20, 21, 26);
  },
  camels: (c) => {
    c.moveTo(5, 20);
    c.quadraticCurveTo(10, 7, 15, 17);
    c.quadraticCurveTo(20, 7, 25, 20);
    line(c, 9, 20, 9, 26);
    line(c, 21, 20, 21, 26);
  },
  artillery: (c) => {
    c.moveTo(21, 16);
    c.arc(16, 16, 5, 0, Math.PI * 2);
  },
  siege_engine: (c) => {
    line(c, 6, 26, 16, 6, 26, 26);
    line(c, 10, 18, 22, 18);
  },
  warship: (c) => {
    c.moveTo(4, 17);
    c.quadraticCurveTo(16, 29, 28, 17);
    line(c, 4, 17, 28, 17);
    line(c, 16, 17, 16, 4);
    line(c, 16, 6, 23, 11, 16, 13);
  },
  transport: (c) => {
    c.moveTo(4, 17);
    c.quadraticCurveTo(16, 29, 28, 17);
    line(c, 4, 17, 28, 17);
    c.rect(11, 9, 10, 8);
  },
  commander: (c) => {
    line(c, 10, 28, 10, 4);
    line(c, 10, 5, 25, 9, 10, 14);
  },
  camp: (c) => {
    line(c, 4, 26, 16, 6, 28, 26, 4, 26);
    line(c, 16, 26, 16, 16);
  },
  baggage: (c) => {
    c.rect(5, 10, 22, 10);
    c.moveTo(13, 24);
    c.arc(10, 24, 3, 0, Math.PI * 2);
    c.moveTo(25, 24);
    c.arc(22, 24, 3, 0, Math.PI * 2);
  },
};

const NOTE_GLYPHS: Record<string, Draw> = {
  clash: (c) => {
    line(c, 7, 7, 25, 25);
    line(c, 25, 7, 7, 25);
    line(c, 6, 18, 14, 26);
    line(c, 26, 18, 18, 26);
  },
  death: (c) => {
    line(c, 16, 5, 16, 27);
    line(c, 9, 12, 23, 12);
  },
  capture: (c) => {
    line(c, 10, 28, 10, 4);
    line(c, 10, 5, 25, 9, 10, 14);
  },
  event: (c) => {
    c.moveTo(20, 16);
    c.arc(16, 16, 4, 0, Math.PI * 2);
  },
};

function canvas(): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const el = document.createElement('canvas');
  el.width = el.height = SIZE * RATIO;
  const ctx = el.getContext('2d') as CanvasRenderingContext2D;
  ctx.scale(RATIO, RATIO);
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  return [el, ctx];
}

/** Stroke a glyph white over a dark halo. */
function strokeGlyph(ctx: CanvasRenderingContext2D, draw: Draw, scale = 1, halo = true): void {
  ctx.save();
  if (scale !== 1) {
    ctx.translate(SIZE / 2, SIZE / 2);
    ctx.scale(scale, scale);
    ctx.translate(-SIZE / 2, -SIZE / 2);
  }
  if (halo) {
    ctx.beginPath();
    draw(ctx);
    ctx.strokeStyle = 'rgba(20,18,15,0.85)';
    ctx.lineWidth = 5.5;
    ctx.stroke();
  }
  ctx.beginPath();
  draw(ctx);
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 2.6;
  ctx.stroke();
  ctx.restore();
}

function add(map: MapLibreMap, id: string, el: HTMLCanvasElement): void {
  if (map.hasImage(id)) return;
  const data = (el.getContext('2d') as CanvasRenderingContext2D).getImageData(0, 0, el.width, el.height);
  map.addImage(id, data, { pixelRatio: RATIO });
}

export const unitGlyphId = (kind: string) => `story-glyph-${GLYPHS[kind] ? kind : 'infantry'}`;
export const pinId = (kind: string, color: string) => `story-pin-${kind}-${color}`;
export const arrowId = (color: string) => `story-arrow-${color}`;
export const noteId = (kind: string) => `story-note-${NOTE_GLYPHS[kind] ? kind : 'label'}`;

/**
 * Register every image a story needs (idempotent; images live in the style, so
 * call again after a basemap switch).
 */
export function registerStoryImages(map: MapLibreMap, sideColors: string[]): void {
  for (const kind of Object.keys(GLYPHS)) {
    const id = unitGlyphId(kind);
    if (map.hasImage(id)) continue;
    const [el, ctx] = canvas();
    strokeGlyph(ctx, GLYPHS[kind]);
    add(map, id, el);
  }

  for (const color of sideColors) {
    for (const kind of ['commander', 'camp', 'baggage']) {
      const id = pinId(kind, color);
      if (map.hasImage(id)) continue;
      const [el, ctx] = canvas();
      ctx.beginPath();
      ctx.arc(16, 16, 13.5, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.lineWidth = 2.5;
      ctx.strokeStyle = '#ffffff';
      ctx.stroke();
      strokeGlyph(ctx, GLYPHS[kind], 0.62, false);
      add(map, id, el);
    }

    const aid = arrowId(color);
    if (!map.hasImage(aid)) {
      // Points north; the layer rotates it to the arrow's last bearing.
      const [el, ctx] = canvas();
      ctx.beginPath();
      line(ctx, 16, 3, 28, 27, 16, 21, 4, 27);
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = 'rgba(255,255,255,0.9)';
      ctx.stroke();
      add(map, aid, el);
    }
  }

  for (const kind of Object.keys(NOTE_GLYPHS)) {
    const id = noteId(kind);
    if (map.hasImage(id)) continue;
    const [el, ctx] = canvas();
    ctx.beginPath();
    ctx.arc(16, 16, 13, 0, Math.PI * 2);
    ctx.fillStyle = '#7c2d12';
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#fde68a';
    ctx.stroke();
    strokeGlyph(ctx, NOTE_GLYPHS[kind], 0.6, false);
    add(map, id, el);
  }
}
