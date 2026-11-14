import type { EraTheme } from '@/lib/era/types';

/** Steel grey and red on dossier graph paper. */
const theme: EraTheme = {
  id: 'cold-war',
  paper: '#e8eaec',
  ink: '#1e2328',
  accent: '#c0392b',
  night: '#1a1e22',
  font: { family: "'Special Elite', 'Geist Mono Variable', monospace", load: () => import('@fontsource/special-elite/index.css') },
  texture: { kind: 'grid', color: '#4a5a6a', ui: 0.2, map: 0.08 },
  ornament: 'dashes',
  map: {
    border: '#c0392b',
    borderWidth: 1.2,
    borderDash: [4,  2],
    land: { color: '#8f9aa3', opacity: 0.12 },
    sea: { color: '#4a5c6b', opacity: 0.16 },
  },
};

export default theme;
