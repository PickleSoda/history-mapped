import type { EraTheme } from '@/lib/era/types';

/** Rice paper, vermilion and jade. */
const theme: EraTheme = {
  id: 'imperial-china',
  paper: '#f6efe2',
  ink: '#222020',
  accent: '#b22a1e',
  accent2: '#2f7a5c',
  night: '#1e1a19',
  texture: { kind: 'linen', color: '#9a8a70', ui: 0.21, map: 0.14 },
  ornament: 'meander',
  map: {
    border: '#b22a1e',
    borderWidth: 1.25,
    land: { color: '#ecdcc0', opacity: 0.14 },
    sea: { color: '#4f8f8a', opacity: 0.14 },
  },
};

export default theme;
