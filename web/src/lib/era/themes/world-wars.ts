import type { EraTheme } from '@/lib/era/types';

/** Grey and red, a printed halftone. */
const theme: EraTheme = {
  id: 'world-wars',
  paper: '#ecebe7',
  ink: '#1f1f1f',
  accent: '#b3261e',
  night: '#1c1c1c',
  font: { family: "'Oswald Variable', 'Geist Variable', sans-serif", load: () => import('@fontsource-variable/oswald/index.css') },
  texture: { kind: 'halftone', color: '#3a3a3a', ui: 0.15, map: 0.1 },
  ornament: 'stripes',
  map: {
    border: '#b3261e',
    borderWidth: 1.35,
    borderOpacity: 0.95,
    land: { color: '#9a9a96', opacity: 0.12 },
    sea: { color: '#5a6670', opacity: 0.15 },
  },
};

export default theme;
