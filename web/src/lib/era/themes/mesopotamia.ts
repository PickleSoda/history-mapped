import type { EraTheme } from '@/lib/era/types';

/** Sun-dried clay and glazed-brick blue (the Ishtar Gate). */
const theme: EraTheme = {
  id: 'mesopotamia',
  paper: '#efdcc0',
  ink: '#3a2a1a',
  accent: '#2e6f8e',
  accent2: '#b07a2a',
  night: '#261b10',
  font: { family: "'Marcellus', 'Fraunces Variable', serif", load: () => import('@fontsource/marcellus/index.css') },
  texture: { kind: 'grain', color: '#8a6440', ui: 0.24, map: 0.2 },
  ornament: 'wedges',
  map: {
    border: '#8b5a2b',
    borderWidth: 1.3,
    borderDash: [2,  1],
    land: { color: '#cfae80', opacity: 0.16 },
    sea: { color: '#4f8a8f', opacity: 0.12 },
  },
};

export default theme;
