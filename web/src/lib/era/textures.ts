import type { TextureKind } from '@/lib/era/types';

/**
 * Procedural, seamlessly tiling textures drawn on a canvas: nothing to
 * download, and only the active era's texture is ever drawn. Each one is a
 * transparent tile whose marks are drawn in one colour with varying alpha, so
 * the same tile works as a CSS background over the UI and as a MapLibre fill
 * pattern over the land.
 */
export const TEXTURE_SIZE = 256;

/** Deterministic PRNG (mulberry32), so a texture looks the same every time. */
function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Tileable value noise with the given lattice period (a divisor of the size). */
function valueNoise(size: number, period: number, rand: () => number): Float32Array {
  const lattice = Float32Array.from({ length: period * period }, rand);
  const out = new Float32Array(size * size);
  const cell = size / period;
  const smooth = (t: number) => t * t * (3 - 2 * t);
  for (let y = 0; y < size; y++) {
    const gy = y / cell;
    const y0 = Math.floor(gy) % period;
    const y1 = (y0 + 1) % period;
    const ty = smooth(gy - Math.floor(gy));
    for (let x = 0; x < size; x++) {
      const gx = x / cell;
      const x0 = Math.floor(gx) % period;
      const x1 = (x0 + 1) % period;
      const tx = smooth(gx - Math.floor(gx));
      const a = lattice[y0 * period + x0] + (lattice[y0 * period + x1] - lattice[y0 * period + x0]) * tx;
      const b = lattice[y1 * period + x0] + (lattice[y1 * period + x1] - lattice[y1 * period + x0]) * tx;
      out[y * size + x] = a + (b - a) * ty;
    }
  }
  return out;
}

/** Fractal noise: octaves of value noise, normalised to 0..1. */
function fbm(size: number, periods: number[], rand: () => number): Float32Array {
  const out = new Float32Array(size * size);
  let total = 0;
  periods.forEach((p, i) => {
    const amp = 1 / 2 ** i;
    total += amp;
    const layer = valueNoise(size, p, rand);
    for (let k = 0; k < out.length; k++) out[k] += layer[k] * amp;
  });
  for (let k = 0; k < out.length; k++) out[k] /= total;
  return out;
}

const clamp = (v: number) => Math.max(0, Math.min(255, v));

/** Per-pixel alpha (0..255) for one texture kind. */
export function textureAlpha(kind: TextureKind, size = TEXTURE_SIZE): Uint8ClampedArray {
  const rand = rng(kind.split('').reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7));
  const n = size * size;
  const alpha = new Uint8ClampedArray(n);
  const speck = () => (rand() < 0.04 ? rand() * 90 : 0);
  const tau = Math.PI * 2;

  switch (kind) {
    case 'grain': {
      for (let k = 0; k < n; k++) alpha[k] = clamp(rand() ** 3 * 70 + speck());
      break;
    }
    case 'sand': {
      const low = fbm(size, [4, 8, 16], rand);
      for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
          const k = y * size + x;
          // Wind ripples: diagonal bands, bent by the noise.
          const ripple = Math.sin(((x + y * 0.5) / size) * tau * 6 + low[k] * 5) * 0.5 + 0.5;
          alpha[k] = clamp(ripple ** 4 * 45 + rand() ** 4 * 80 + low[k] * 20);
        }
      }
      break;
    }
    case 'dirt': {
      const clumps = fbm(size, [8, 16, 32, 64], rand);
      for (let k = 0; k < n; k++) {
        const c = clumps[k];
        alpha[k] = clamp((c > 0.55 ? (c - 0.55) * 360 : c * 30) + rand() ** 6 * 140 + speck());
      }
      // Pebbles: small rings, wrapped at the edges.
      for (let i = 0; i < 26; i++) {
        const cx = rand() * size;
        const cy = rand() * size;
        const r = 1.5 + rand() * 3.5;
        for (let dy = -r - 1; dy <= r + 1; dy++) {
          for (let dx = -r - 1; dx <= r + 1; dx++) {
            const d = Math.hypot(dx, dy);
            if (d > r + 1) continue;
            const x = (Math.round(cx + dx) + size) % size;
            const y = (Math.round(cy + dy) + size) % size;
            const k = y * size + x;
            alpha[k] = clamp(alpha[k] + (d > r - 1 ? 120 : 35));
          }
        }
      }
      break;
    }
    case 'marble': {
      const warp = fbm(size, [4, 8, 16, 32], rand);
      for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
          const k = y * size + x;
          const v = Math.abs(Math.sin(((x + y) / size) * tau * 2 + warp[k] * 9));
          alpha[k] = clamp((1 - v) ** 10 * 150 + warp[k] * 22);
        }
      }
      break;
    }
    case 'parchment': {
      const blotch = fbm(size, [2, 4, 8, 16], rand);
      for (let k = 0; k < n; k++) alpha[k] = clamp(Math.max(0, blotch[k] - 0.35) * 150 + rand() ** 5 * 50 + speck());
      // Fibres: short faint strokes.
      for (let i = 0; i < 140; i++) {
        let x = rand() * size;
        let y = rand() * size;
        const a = rand() * tau;
        for (let s = 0; s < 6 + rand() * 10; s++) {
          const k = ((Math.round(y) + size) % size) * size + ((Math.round(x) + size) % size);
          alpha[k] = clamp(alpha[k] + 28);
          x += Math.cos(a);
          y += Math.sin(a);
        }
      }
      break;
    }
    case 'linen': {
      const rows = Array.from({ length: size }, rand);
      const cols = Array.from({ length: size }, rand);
      for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
          alpha[y * size + x] = clamp((rows[y] ** 3 + cols[x] ** 3) * 40 + rand() ** 6 * 40);
        }
      }
      break;
    }
    case 'halftone': {
      const shade = fbm(size, [2, 4, 8], rand);
      const step = 8;
      for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
          const cx = Math.floor(x / step) * step + step / 2;
          const cy = Math.floor(y / step) * step + step / 2;
          const k = y * size + x;
          const r = 0.6 + shade[k] * 3.2;
          alpha[k] = Math.hypot(x - cx, y - cy) <= r ? 110 : 0;
        }
      }
      break;
    }
    case 'grid': {
      for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
          const major = x % 64 === 0 || y % 64 === 0;
          const minor = x % 16 === 0 || y % 16 === 0;
          alpha[y * size + x] = clamp((major ? 90 : minor ? 40 : 0) + rand() ** 8 * 40);
        }
      }
      break;
    }
    case 'ripples': {
      const drops = Array.from({ length: 7 }, () => [rand() * size, rand() * size, 30 + rand() * 60]);
      const calm = fbm(size, [4, 8], rand);
      for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
          let v = 0;
          for (const [cx, cy, reach] of drops) {
            // Nearest copy of the drop, so the rings wrap across the tile edge.
            const dx = Math.min(Math.abs(x - cx), size - Math.abs(x - cx));
            const dy = Math.min(Math.abs(y - cy), size - Math.abs(y - cy));
            const d = Math.hypot(dx, dy);
            v += Math.max(0, Math.cos(d * 0.55)) ** 6 * Math.exp(-d / reach);
          }
          alpha[y * size + x] = clamp(v * 120 + calm[y * size + x] * 25);
        }
      }
      break;
    }
    case 'tiles': {
      // Eight-pointed star lattice, as in Islamic tilework.
      const cell = 64;
      for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
          const u = (x % cell) - cell / 2;
          const v = (y % cell) - cell / 2;
          const square = Math.max(Math.abs(u), Math.abs(v));
          const diamond = (Math.abs(u) + Math.abs(v)) / Math.SQRT2;
          const star = Math.max(Math.min(square, diamond), Math.min(Math.abs(u), Math.abs(v)) * 1.4);
          const edge = Math.abs(Math.max(square, diamond) - 18) < 1.2 || Math.abs(star - 26) < 1;
          alpha[y * size + x] = clamp((edge ? 120 : 0) + rand() ** 8 * 30);
        }
      }
      break;
    }
    case 'mosaic': {
      const cell = 8;
      const tint = Array.from({ length: (size / cell) ** 2 }, rand);
      for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
          const grout = x % cell === 0 || y % cell === 0;
          const t = tint[Math.floor(y / cell) * (size / cell) + Math.floor(x / cell)];
          alpha[y * size + x] = clamp(grout ? 120 : t * 45);
        }
      }
      break;
    }
  }
  return alpha;
}

function hexRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.replace('#', ''), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** The texture as RGBA pixels in `color`, its alpha scaled by `strength`. */
export function textureImage(kind: TextureKind, color: string, strength = 1, size = TEXTURE_SIZE): ImageData | null {
  if (typeof ImageData === 'undefined') return null;
  const alpha = textureAlpha(kind, size);
  const [r, g, b] = hexRgb(color);
  const data = new Uint8ClampedArray(size * size * 4);
  for (let k = 0; k < alpha.length; k++) {
    data[k * 4] = r;
    data[k * 4 + 1] = g;
    data[k * 4 + 2] = b;
    data[k * 4 + 3] = alpha[k] * strength;
  }
  return new ImageData(data, size, size);
}

const urls = new Map<string, Promise<string | null>>();

/**
 * The texture as an object URL for a CSS background, its strength baked into
 * the alpha (cached per kind, colour and strength).
 */
export function textureUrl(kind: TextureKind, color: string, strength: number): Promise<string | null> {
  const key = `${kind}:${color}:${strength}`;
  let url = urls.get(key);
  if (!url) {
    url = new Promise((resolve) => {
      const image = textureImage(kind, color, strength);
      const canvas = typeof document !== 'undefined' ? document.createElement('canvas') : null;
      const ctx = canvas?.getContext('2d');
      if (!image || !canvas || !ctx) return resolve(null);
      canvas.width = image.width;
      canvas.height = image.height;
      ctx.putImageData(image, 0, 0);
      canvas.toBlob((blob) => resolve(blob ? URL.createObjectURL(blob) : null), 'image/png');
    });
    urls.set(key, url);
  }
  return url;
}
