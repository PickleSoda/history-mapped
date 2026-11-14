import type { EraTheme } from '@/lib/era/types';

/** Clay and bronze, with a fine grain. */
const theme: EraTheme = {
  id: 'bronze-age',
  paper: '#f3e6cc',
  ink: '#3a2716',
  accent: '#a8642a',
  night: '#261a10',
  font: { family: "'Marcellus', 'Fraunces Variable', serif", load: () => import('@fontsource/marcellus/index.css') },
  texture: { kind: 'grain', color: '#7a5530', ui: 0.21, map: 0.16 },
  ornament: 'zigzag',
  map: {
    border: '#9a5b2a',
    borderWidth: 1.15,
    land: { color: '#d0a060', opacity: 0.1 },
    sea: { color: '#5f8f8a', opacity: 0.1 },
  },
};

export default theme;
