import type { EraTheme } from '@/lib/era/types';

/** Off-white travertine, imperial crimson and fluted columns. */
const theme: EraTheme = {
  id: 'rome',
  paper: '#f5f1e8',
  ink: '#2a2622',
  accent: '#7b1e2b',
  accent2: '#b08d3c',
  night: '#231f1c',
  font: { family: "'Cinzel Variable', 'Fraunces Variable', serif", load: () => import('@fontsource-variable/cinzel/index.css') },
  texture: { kind: 'marble', color: '#a39a8c', ui: 0.28, map: 0.2 },
  ornament: 'dentil',
  map: {
    border: '#7b1e2b',
    borderWidth: 1.4,
    land: { color: '#ece4d4', opacity: 0.14 },
    sea: { color: '#4a7f9a', opacity: 0.12 },
  },
};

export default theme;
