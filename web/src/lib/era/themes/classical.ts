import type { EraTheme } from '@/lib/era/types';

/** Warm marble and terracotta. */
const theme: EraTheme = {
  id: 'classical',
  paper: '#f6f1e7',
  ink: '#2c2a26',
  accent: '#8c3b2e',
  night: '#262320',
  font: { family: "'Cinzel Variable', 'Fraunces Variable', serif", load: () => import('@fontsource-variable/cinzel/index.css') },
  texture: { kind: 'marble', color: '#9a9286', ui: 0.24, map: 0.2 },
  ornament: 'meander',
  map: {
    border: '#8c3b2e',
    borderWidth: 1.15,
    land: { color: '#e9dfcc', opacity: 0.12 },
    sea: { color: '#4f86a0', opacity: 0.12 },
  },
};

export default theme;
