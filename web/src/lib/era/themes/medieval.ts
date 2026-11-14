import type { EraTheme } from '@/lib/era/types';

/** Parchment, brown ink and red rubrics. */
const theme: EraTheme = {
  id: 'medieval',
  paper: '#f1e6cf',
  ink: '#2f2418',
  accent: '#8e2a1f',
  accent2: '#1f3d6b',
  night: '#221a12',
  font: { family: "'Grenze Gotisch Variable', 'Fraunces Variable', serif", load: () => import('@fontsource-variable/grenze-gotisch/index.css') },
  texture: { kind: 'parchment', color: '#8a6a3e', ui: 0.28, map: 0.22 },
  ornament: 'knot',
  map: {
    border: '#6b4423',
    borderWidth: 1.1,
    borderBlur: 0.4,
    borderDash: [3,  1.5],
    land: { color: '#d9c49a', opacity: 0.12 },
    sea: { color: '#5d7f87', opacity: 0.12 },
  },
};

export default theme;
