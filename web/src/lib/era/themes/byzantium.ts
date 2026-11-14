import type { EraTheme } from '@/lib/era/types';

/** Imperial purple, gold and mosaic tesserae. */
const theme: EraTheme = {
  id: 'byzantium',
  paper: '#f3ecdf',
  ink: '#2a1f2e',
  accent: '#5b2a6e',
  accent2: '#b8912f',
  night: '#201824',
  font: { family: "'Uncial Antiqua', 'Fraunces Variable', serif", load: () => import('@fontsource/uncial-antiqua/index.css') },
  texture: { kind: 'mosaic', color: '#8a7a5a', ui: 0.21, map: 0.14 },
  ornament: 'dots',
  map: {
    border: '#5b2a6e',
    borderWidth: 1.3,
    land: { color: '#e6d9c3', opacity: 0.14 },
    sea: { color: '#3f6f8f', opacity: 0.14 },
  },
};

export default theme;
