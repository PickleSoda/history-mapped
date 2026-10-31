/**
 * Battle-map symbols, drawn on a canvas and registered as map images.
 *
 * The glyph language follows military map convention loosely: foot are a
 * cross (X), horse a single diagonal, missile troops their weapon, artillery a
 * dot; heavier troops get a frame. Glyphs are white with a dark halo so they
 * read on any side colour. Pins (commander, camp, baggage), standards, ships,
 * arrowheads, hatching and captured flags are coloured per side or
 * contingent, so their image ids carry the colour. Unit-state overlays
 * (killed, wounded, sunk, burning) and feature-state badges sit on top.
 * Campaign-scale markers (army, fleet, caravan, merchant ship, expedition,
 * group) are pins with their glyph.
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
  standard: (c) => {
    line(c, 12, 29, 12, 3);
    line(c, 12, 4, 27, 7, 22, 11, 27, 15, 12, 16);
  },
  ship: (c) => {
    c.moveTo(16, 3);
    c.quadraticCurveTo(25, 12, 22, 29);
    line(c, 22, 29, 10, 29);
    c.quadraticCurveTo(7, 12, 16, 3);
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
  // v3: campaign-scale markers
  army: (c) => {
    line(c, 7, 25, 25, 7);
    line(c, 25, 25, 7, 7);
    line(c, 5, 20, 12, 27);
    line(c, 27, 20, 20, 27);
  },
  fleet: (c) => {
    c.moveTo(4, 17);
    c.quadraticCurveTo(16, 29, 28, 17);
    line(c, 4, 17, 28, 17);
    line(c, 16, 17, 16, 4);
    line(c, 16, 6, 23, 11, 16, 13);
  },
  merchant_ship: (c) => {
    c.moveTo(4, 18);
    c.quadraticCurveTo(16, 29, 28, 18);
    line(c, 4, 18, 28, 18);
    line(c, 16, 18, 16, 4);
    c.moveTo(16, 5);
    c.quadraticCurveTo(25, 10, 16, 16);
  },
  caravan: (c) => {
    c.moveTo(5, 20);
    c.quadraticCurveTo(10, 7, 15, 17);
    c.quadraticCurveTo(20, 7, 25, 20);
    line(c, 9, 20, 9, 26);
    line(c, 21, 20, 21, 26);
  },
  expedition: (c) => {
    line(c, 16, 3, 19.5, 12.5, 29, 16, 19.5, 19.5, 16, 29, 12.5, 19.5, 3, 16, 12.5, 12.5, 16, 3);
  },
  group: (c) => {
    for (const x of [9, 16, 23]) {
      c.moveTo(x + 3, 12);
      c.arc(x, 12, 3, 0, Math.PI * 2);
      c.moveTo(x - 5, 25);
      c.quadraticCurveTo(x, 13, x + 5, 25);
    }
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

/** A standard: a pole, and a swallow-tailed cloth filled in the side's colour. */
const pole: Draw = (c) => line(c, 14, 30, 14, 3);
const cloth: Draw = (c) => {
  line(c, 14, 4, 30, 7, 25, 11, 30, 15, 14, 17);
  c.closePath();
};

/** A hull seen from above, bow up (north); the layer rotates it to its facing. */
const hull: Draw = (c) => {
  c.moveTo(16, 2);
  c.quadraticCurveTo(26, 12, 22.5, 30);
  c.lineTo(9.5, 30);
  c.quadraticCurveTo(6, 12, 16, 2);
  c.closePath();
};

const flame: Draw = (c) => {
  c.moveTo(16, 3);
  c.bezierCurveTo(19, 9, 26, 13, 24, 22);
  c.bezierCurveTo(23, 27, 19, 30, 16, 30);
  c.bezierCurveTo(12, 30, 8, 27, 8, 22);
  c.bezierCurveTo(8, 17, 12, 15, 12, 10);
  c.bezierCurveTo(14, 12, 15, 14, 15, 16);
  c.bezierCurveTo(17, 12, 17, 7, 16, 3);
  c.closePath();
};
const flameCore: Draw = (c) => {
  c.moveTo(16, 16);
  c.bezierCurveTo(18, 19, 21, 21, 20, 25);
  c.bezierCurveTo(19, 28, 13, 28, 12, 25);
  c.bezierCurveTo(11, 22, 14, 20, 16, 16);
  c.closePath();
};

/** Badges for a feature's state (`captured` is a flag per colour, `burning` a flame). */
const TERRAIN_STATE_GLYPHS: Record<string, Draw> = {
  contested: NOTE_GLYPHS.clash,
  destroyed: (c) => line(c, 6, 26, 6, 14, 11, 9, 13, 16, 17, 11, 20, 18, 26, 13, 26, 26, 6, 26),
  flooded: (c) => {
    for (const y of [10, 16, 22]) {
      c.moveTo(5, y);
      c.bezierCurveTo(9, y - 4, 12, y + 4, 16, y);
      c.bezierCurveTo(20, y - 4, 23, y + 4, 27, y);
    }
  },
  // v3
  infected: (c) => {
    c.moveTo(22, 16);
    c.arc(16, 16, 6, 0, Math.PI * 2);
    for (let k = 0; k < 8; k++) {
      const a = (k * Math.PI) / 4;
      line(c, 16 + Math.cos(a) * 6, 16 + Math.sin(a) * 6, 16 + Math.cos(a) * 11, 16 + Math.sin(a) * 11);
    }
  },
  peak: (c) => line(c, 4, 26, 12, 9, 17, 18, 21, 13, 28, 26),
  recovered: (c) => line(c, 7, 17, 13, 23, 25, 9),
  founded: (c) => {
    const pts: number[] = [];
    for (let k = 0; k <= 10; k++) {
      const a = -Math.PI / 2 + (k * Math.PI) / 5;
      const r = k % 2 ? 5 : 12;
      pts.push(16 + Math.cos(a) * r, 17 + Math.sin(a) * r);
    }
    line(c, ...pts);
  },
  abandoned: (c) => {
    line(c, 8, 26, 8, 15, 16, 8, 24, 15, 24, 26, 8, 26);
    line(c, 6, 28, 26, 6);
  },
  disrupted: (c) => line(c, 18, 3, 10, 17, 19, 15, 12, 29),
  new: (c) => {
    line(c, 16, 6, 16, 26);
    line(c, 6, 16, 26, 16);
  },
};

/** A state badge's ink (dark, unless the state has a colour of its own). */
const STATE_INK: Record<string, string> = {
  flooded: '#1d4ed8',
  infected: '#b91c1c',
  peak: '#7f1d1d',
  recovered: '#15803d',
  founded: '#a16207',
  disrupted: '#dc2626',
  new: '#0e7490',
};

function canvas(size = SIZE): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const el = document.createElement('canvas');
  el.width = el.height = size * RATIO;
  const ctx = el.getContext('2d') as CanvasRenderingContext2D;
  ctx.scale(RATIO, RATIO);
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  return [el, ctx];
}

/** Stroke a glyph white over a dark halo (or in `color`, without one). */
function strokeGlyph(ctx: CanvasRenderingContext2D, draw: Draw, scale = 1, halo = true, color = '#ffffff'): void {
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
  ctx.strokeStyle = color;
  ctx.lineWidth = 2.6;
  ctx.stroke();
  ctx.restore();
}

/** Fill a closed shape in `color` with a white edge over a dark halo. */
function fillShape(ctx: CanvasRenderingContext2D, draw: Draw, color: string): void {
  ctx.beginPath();
  draw(ctx);
  ctx.strokeStyle = 'rgba(20,18,15,0.85)';
  ctx.lineWidth = 4;
  ctx.stroke();
  ctx.fillStyle = color;
  ctx.fill();
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 1.6;
  ctx.stroke();
}

/** A round badge (terrain state, alternative site) that `paint`s inside. */
function badge(ctx: CanvasRenderingContext2D, paint: () => void, dashed = false): void {
  ctx.beginPath();
  ctx.arc(16, 16, 12.5, 0, Math.PI * 2);
  ctx.fillStyle = dashed ? 'rgba(255,253,245,0.7)' : '#fffdf5';
  ctx.fill();
  ctx.lineWidth = 2;
  ctx.strokeStyle = dashed ? '#78716c' : '#292524';
  if (dashed) ctx.setLineDash([3, 2.5]);
  ctx.stroke();
  ctx.setLineDash([]);
  paint();
}

function add(map: MapLibreMap, id: string, el: HTMLCanvasElement): void {
  if (map.hasImage(id)) return;
  const data = (el.getContext('2d') as CanvasRenderingContext2D).getImageData(0, 0, el.width, el.height);
  map.addImage(id, data, { pixelRatio: RATIO });
}

export const unitGlyphId = (kind: string) => `story-glyph-${GLYPHS[kind] ? kind : 'infantry'}`;
export const pinId = (kind: string, color: string) => `story-pin-${kind}-${color}`;
export const standardId = (color: string) => `story-standard-${color}`;
export const shipId = (color: string) => `story-ship-${color}`;
export const arrowId = (color: string) => `story-arrow-${color}`;
export const ramId = (color: string) => `story-ram-${color}`;
export const landingId = (color: string) => `story-landing-${color}`;
export const noteId = (kind: string) => `story-note-${NOTE_GLYPHS[kind] ? kind : 'label'}`;
/** A unit-state overlay: killed, wounded, sunk, burning (captured is per colour). */
export const stateId = (state: string) => `story-state-${state}`;
export const capturedId = (color: string) => `story-state-captured-${color}`;
/** Diagonal hatching (a fill pattern) for a unit captured by this colour's side. */
export const hatchId = (color: string) => `story-hatch-${color}`;
/** A terrain feature's state badge; `captured` flies the holder's flag. */
export const terrainStateId = (state: string, color: string) =>
  state === 'captured' ? `story-tflag-${color}` : `story-tstate-${state}`;
export const ALT_SITE_ICON = 'story-alt';

/** Pin kinds drawn as a round badge with their glyph. */
const PIN_KINDS = ['commander', 'camp', 'baggage', 'army', 'fleet', 'caravan', 'merchant_ship', 'expedition', 'group'];

/**
 * Register every image a story needs (idempotent; images live in the style, so
 * call again after a basemap switch).
 */
export function registerStoryImages(map: MapLibreMap, colors: string[]): void {
  for (const kind of Object.keys(GLYPHS)) {
    const id = unitGlyphId(kind);
    if (map.hasImage(id)) continue;
    const [el, ctx] = canvas();
    strokeGlyph(ctx, GLYPHS[kind]);
    add(map, id, el);
  }

  for (const color of colors) {
    for (const kind of PIN_KINDS) {
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
    perColor(map, color);
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

  const once = (id: string, draw: (ctx: CanvasRenderingContext2D) => void) => {
    if (map.hasImage(id)) return;
    const [el, ctx] = canvas();
    draw(ctx);
    add(map, id, el);
  };
  once(stateId('killed'), (ctx) => {
    const x: Draw = (c) => {
      line(c, 6, 6, 26, 26);
      line(c, 26, 6, 6, 26);
    };
    strokeGlyph(ctx, x, 1, true, '#b91c1c');
  });
  once(stateId('wounded'), (ctx) => {
    ctx.beginPath();
    ctx.arc(16, 16, 8, 0, Math.PI * 2);
    ctx.fillStyle = '#ffffff';
    ctx.fill();
    ctx.lineWidth = 1.2;
    ctx.strokeStyle = 'rgba(20,18,15,0.6)';
    ctx.stroke();
    ctx.beginPath();
    line(ctx, 16, 11, 16, 21);
    line(ctx, 11, 16, 21, 16);
    ctx.strokeStyle = '#dc2626';
    ctx.lineWidth = 3.2;
    ctx.lineCap = 'butt';
    ctx.stroke();
  });
  once(stateId('sunk'), (ctx) =>
    strokeGlyph(ctx, (c) => {
      // A tilted, broken hull over the waves.
      c.moveTo(5, 12);
      c.quadraticCurveTo(14, 22, 26, 17);
      line(c, 26, 17, 5, 12);
      line(c, 15, 16, 11, 5);
      for (const y of [23, 28]) {
        c.moveTo(4, y);
        c.bezierCurveTo(9, y - 3, 12, y + 3, 16, y);
        c.bezierCurveTo(20, y - 3, 23, y + 3, 28, y);
      }
    }),
  );
  once(stateId('burning'), (ctx) => {
    fillShape(ctx, flame, '#f97316');
    ctx.beginPath();
    flameCore(ctx);
    ctx.fillStyle = '#fde047';
    ctx.fill();
  });
  for (const [state, draw] of Object.entries(TERRAIN_STATE_GLYPHS)) {
    once(terrainStateId(state, ''), (ctx) =>
      badge(ctx, () => strokeGlyph(ctx, draw, 0.62, false, STATE_INK[state] ?? '#292524')),
    );
  }
  once(terrainStateId('burning', ''), (ctx) =>
    badge(ctx, () => {
      ctx.save();
      ctx.translate(16, 16);
      ctx.scale(0.62, 0.62);
      ctx.translate(-16, -16);
      fillShape(ctx, flame, '#f97316');
      ctx.restore();
    }),
  );
  once(ALT_SITE_ICON, (ctx) =>
    badge(
      ctx,
      () => {
        ctx.fillStyle = '#57534e';
        ctx.font = 'bold 17px system-ui, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('?', 16, 17);
      },
      true,
    ),
  );
}

/** The images drawn in one side's (or contingent's) colour. */
function perColor(map: MapLibreMap, color: string): void {
  const once = (id: string, draw: (ctx: CanvasRenderingContext2D) => void, size = SIZE) => {
    if (map.hasImage(id)) return;
    const [el, ctx] = canvas(size);
    draw(ctx);
    add(map, id, el);
  };
  once(standardId(color), (ctx) => {
    strokeGlyph(ctx, pole);
    fillShape(ctx, cloth, color);
  });
  once(shipId(color), (ctx) => {
    fillShape(ctx, hull, color);
    ctx.beginPath();
    line(ctx, 16, 9, 16, 25);
    ctx.strokeStyle = 'rgba(255,255,255,0.85)';
    ctx.lineWidth = 1.4;
    ctx.stroke();
  });
  // Points north; the layer rotates it to the arrow's last bearing.
  once(ramId(color), (ctx) =>
    fillShape(ctx, (c) => {
      line(c, 16, 1, 22, 13, 19, 13, 19, 20, 25, 25, 7, 25, 13, 20, 13, 13, 10, 13);
      c.closePath();
    }, color),
  );
  once(landingId(color), (ctx) => {
    fillShape(ctx, (c) => {
      line(c, 16, 12, 25, 29, 16, 24, 7, 29);
      c.closePath();
    }, color);
    // The beach the arrow lands on.
    strokeGlyph(ctx, (c) => line(c, 3, 10, 16, 3, 29, 10), 1, true, color);
  });
  // Hatching for a unit this side captured, as a body fill pattern and a pin overlay.
  once(hatchId(color), (ctx) => {
    ctx.beginPath();
    for (let k = -16; k <= 32; k += 8) line(ctx, k, 0, k - 16, 16);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.6;
    ctx.lineCap = 'butt';
    ctx.stroke();
  }, 16);
  once(capturedId(color), (ctx) => {
    ctx.save();
    ctx.beginPath();
    ctx.arc(16, 16, 13, 0, Math.PI * 2);
    ctx.clip();
    ctx.beginPath();
    for (let k = -32; k <= 64; k += 6) line(ctx, k, 0, k - 32, 32);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.6;
    ctx.stroke();
    ctx.restore();
    ctx.beginPath();
    ctx.arc(16, 16, 13.5, 0, Math.PI * 2);
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = color;
    ctx.stroke();
  });
  once(terrainStateId('captured', color), (ctx) =>
    badge(ctx, () => {
      ctx.save();
      ctx.translate(16, 16);
      ctx.scale(0.62, 0.62);
      ctx.translate(-16, -16);
      strokeGlyph(ctx, pole, 1, false, '#292524');
      fillShape(ctx, cloth, color);
      ctx.restore();
    }),
  );
}
