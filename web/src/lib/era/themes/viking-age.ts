import type { EraTheme } from '@/lib/era/types';

/** Cold slate and rust, carved knotwork. */
const theme: EraTheme = {
  id: 'viking-age',
  paper: '#e9ecee',
  ink: '#1e2a33',
  accent: '#3a5f7d',
  accent2: '#8a3a2a',
  night: '#151c22',
  texture: { kind: 'grain', color: '#4d5a63', ui: 0.22, map: 0.16 },
  ornament: 'knot',
  map: {
    border: '#3a5f7d',
    borderWidth: 1.2,
    land: { color: '#c9d1d6', opacity: 0.14 },
    sea: { color: '#2f5f80', opacity: 0.18 },
  },
};

export default theme;
