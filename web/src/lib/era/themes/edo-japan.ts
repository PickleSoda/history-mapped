import type { EraTheme } from '@/lib/era/types';

/** Indigo on washi paper, seigaiha waves. */
const theme: EraTheme = {
  id: 'edo-japan',
  paper: '#f4efe4',
  ink: '#1f2433',
  accent: '#2c3e6b',
  accent2: '#b23a2a',
  night: '#171b26',
  texture: { kind: 'linen', color: '#8a8070', ui: 0.2, map: 0.12 },
  ornament: 'waves',
  map: {
    border: '#2c3e6b',
    borderWidth: 1.2,
    land: { color: '#e6dcc6', opacity: 0.12 },
    sea: { color: '#2c5a8a', opacity: 0.16 },
  },
};

export default theme;
