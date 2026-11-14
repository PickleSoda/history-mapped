import type { EraTheme } from '@/lib/era/types';

/** Chart paper, navy ink and red rhumb lines. */
const theme: EraTheme = {
  id: 'age-of-sail',
  paper: '#f2ead9',
  ink: '#26303a',
  accent: '#1f4e79',
  accent2: '#8a3324',
  night: '#1b2129',
  font: { family: "'IM Fell English', 'Fraunces Variable', serif", load: () => import('@fontsource/im-fell-english/index.css') },
  texture: { kind: 'linen', color: '#7d6c50', ui: 0.21, map: 0.14 },
  ornament: 'waves',
  map: {
    border: '#8a3324',
    borderWidth: 1.0,
    land: { color: '#e3d4b0', opacity: 0.12 },
    sea: { color: '#3f7aa0', opacity: 0.16 },
  },
};

export default theme;
