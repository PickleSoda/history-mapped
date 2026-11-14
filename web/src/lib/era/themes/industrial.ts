import type { EraTheme } from '@/lib/era/types';

/** Soot, brass and deep green. */
const theme: EraTheme = {
  id: 'industrial',
  paper: '#eeebe4',
  ink: '#23221f',
  accent: '#2f5d50',
  accent2: '#a07a2c',
  night: '#1d1d1b',
  font: { family: "'Playfair Display Variable', 'Fraunces Variable', serif", load: () => import('@fontsource-variable/playfair-display/index.css') },
  texture: { kind: 'linen', color: '#55524c', ui: 0.21, map: 0.12 },
  ornament: 'rivets',
  map: {
    border: '#2f5d50',
    borderWidth: 1.2,
    land: { color: '#c9c4b8', opacity: 0.1 },
    sea: { color: '#4d6f80', opacity: 0.14 },
  },
};

export default theme;
