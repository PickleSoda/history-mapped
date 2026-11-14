import type { EraTheme } from '@/lib/era/types';

/** Desert sand, lapis and gold. */
const theme: EraTheme = {
  id: 'egypt',
  paper: '#f4e4c1',
  ink: '#3b2a14',
  accent: '#1e5b8a',
  accent2: '#c8962e',
  night: '#2a1f10',
  font: { family: "'Marcellus', 'Fraunces Variable', serif", load: () => import('@fontsource/marcellus/index.css') },
  texture: { kind: 'sand', color: '#b08646', ui: 0.29, map: 0.18 },
  ornament: 'lotus',
  pillar: 'fluting',
  map: {
    border: '#b4762b',
    borderWidth: 1.4,
    borderDash: [2,  1],
    land: { color: '#e2c58a', opacity: 0.2 },
    sea: { color: '#3f8fa6', opacity: 0.14 },
  },
};

export default theme;
