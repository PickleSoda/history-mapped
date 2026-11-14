import type { EraTheme } from '@/lib/era/types';

/** Turquoise tilework and gold. */
const theme: EraTheme = {
  id: 'islamic-golden-age',
  paper: '#f2ecdc',
  ink: '#1f2a2a',
  accent: '#0f6f6a',
  accent2: '#b8862b',
  night: '#142020',
  font: { family: "'Amiri', 'Fraunces Variable', serif", load: () => import('@fontsource/amiri/index.css') },
  texture: { kind: 'tiles', color: '#2f6f6a', ui: 0.21, map: 0.14 },
  ornament: 'arabesque',
  map: {
    border: '#0f6f6a',
    borderWidth: 1.25,
    land: { color: '#e6d7b5', opacity: 0.14 },
    sea: { color: '#2a8a8a', opacity: 0.14 },
  },
};

export default theme;
