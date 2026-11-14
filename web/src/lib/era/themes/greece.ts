import type { EraTheme } from '@/lib/era/types';

/** White marble and Aegean blue. */
const theme: EraTheme = {
  id: 'greece',
  paper: '#f7f5ef',
  ink: '#1f2a36',
  accent: '#1d5fa0',
  night: '#1b222b',
  font: { family: "'Marcellus', 'Fraunces Variable', serif", load: () => import('@fontsource/marcellus/index.css') },
  texture: { kind: 'marble', color: '#8d97a3', ui: 0.24, map: 0.18 },
  ornament: 'meander',
  map: {
    border: '#1d5fa0',
    borderWidth: 1.25,
    land: { color: '#efe9dc', opacity: 0.14 },
    sea: { color: '#2b7fc0', opacity: 0.18 },
  },
};

export default theme;
