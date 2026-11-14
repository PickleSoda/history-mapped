import type { EraTheme } from '@/lib/era/types';

/** Clear blues and a pond-ripple texture. */
const theme: EraTheme = {
  id: 'global-age',
  paper: '#f3f7fa',
  ink: '#1b2733',
  accent: '#1f7a9c',
  night: '#141c24',
  texture: { kind: 'ripples', color: '#3d7fa6', ui: 0.21, map: 0.12 },
  ornament: 'waves',
  map: {
    border: '#1f7a9c',
    borderWidth: 1.0,
    land: { color: '#d8e6ee', opacity: 0.1 },
    sea: { color: '#2f8fbf', opacity: 0.15 },
  },
};

export default theme;
