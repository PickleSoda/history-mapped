import type { EraTheme } from '@/lib/era/types';

/** Earth and ochre, a dirt texture: the long ages before writing. */
const theme: EraTheme = {
  id: 'prehistory',
  paper: '#efe4d2',
  ink: '#3b2a1d',
  accent: '#8b5a2b',
  night: '#241a12',
  texture: { kind: 'dirt', color: '#5a3d22', ui: 0.2, map: 0.22 },
  ornament: 'dots',
  map: {
    border: '#7a4b26',
    borderWidth: 1.1,
    borderOpacity: 0.85,
    land: { color: '#b98b5e', opacity: 0.12 },
    sea: { color: '#6f7f6a', opacity: 0.14 },
  },
};

export default theme;
