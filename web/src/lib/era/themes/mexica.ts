import type { EraTheme } from '@/lib/era/types';

/** Jade, turquoise and red, a stepped fret. */
const theme: EraTheme = {
  id: 'mexica',
  paper: '#f3e9d6',
  ink: '#2a2018',
  accent: '#1f7a6e',
  accent2: '#b23a1e',
  night: '#1f1812',
  texture: { kind: 'grain', color: '#7a6040', ui: 0.21, map: 0.16 },
  ornament: 'steps',
  map: {
    border: '#b23a1e',
    borderWidth: 1.3,
    land: { color: '#dcc79e', opacity: 0.14 },
    sea: { color: '#2f8f86', opacity: 0.14 },
  },
};

export default theme;
