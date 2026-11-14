import type { EraTheme } from '@/lib/era/types';

/** Burgundy, racing green and filigree. */
const theme: EraTheme = {
  id: 'victorian',
  paper: '#f1ebdf',
  ink: '#2a1f1a',
  accent: '#5e1f2a',
  accent2: '#2f4f3a',
  night: '#1e1814',
  font: { family: "'Playfair Display Variable', 'Fraunces Variable', serif", load: () => import('@fontsource-variable/playfair-display/index.css') },
  texture: { kind: 'linen', color: '#7a5a4a', ui: 0.22, map: 0.14 },
  ornament: 'filigree',
  map: {
    border: '#5e1f2a',
    borderWidth: 1.3,
    land: { color: '#ddd0b8', opacity: 0.14 },
    sea: { color: '#4a6a7a', opacity: 0.14 },
  },
};

export default theme;
