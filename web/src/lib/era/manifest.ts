import type { Box, EraEntry } from '@/lib/era/types';

/**
 * Where and when each era theme applies. This file is the only part of the
 * era themes in the main bundle: each theme's palette, fonts, textures and map
 * styling live in themes/<theme>.ts and load on first use.
 *
 * The global eras tile the whole timeline, from the deep past (earth browns,
 * a dirt texture) to the present (clear blues, a pond texture). A regional era
 * takes over when the map is zoomed in on its region during its years.
 */
export const GLOBAL_ERAS: EraEntry[] = [
  { id: 'prehistory', label: 'Prehistory', theme: 'prehistory', start: -100000, end: -3001, swatch: ['#efe4d2', '#8b5a2b'] },
  { id: 'bronze-age', label: 'The Bronze Age', theme: 'bronze-age', start: -3000, end: -801, swatch: ['#f3e6cc', '#a8642a'] },
  { id: 'classical', label: 'Classical Antiquity', theme: 'classical', start: -800, end: 499, swatch: ['#f6f1e7', '#8c3b2e'] },
  { id: 'medieval', label: 'The Middle Ages', theme: 'medieval', start: 500, end: 1449, swatch: ['#f1e6cf', '#8e2a1f'] },
  { id: 'age-of-sail', label: 'The Age of Sail', theme: 'age-of-sail', start: 1450, end: 1799, swatch: ['#f2ead9', '#1f4e79'] },
  { id: 'industrial', label: 'The Industrial Age', theme: 'industrial', start: 1800, end: 1913, swatch: ['#eeebe4', '#2f5d50'] },
  { id: 'world-wars', label: 'The World Wars', theme: 'world-wars', start: 1914, end: 1945, swatch: ['#ecebe7', '#b3261e'] },
  { id: 'cold-war', label: 'The Cold War', theme: 'cold-war', start: 1946, end: 1991, swatch: ['#e8eaec', '#c0392b'] },
  { id: 'global-age', label: 'The Global Age', theme: 'global-age', start: 1992, end: 100000, swatch: ['#f3f7fa', '#1f7a9c'] },
];

export const REGIONAL_ERAS: EraEntry[] = [
  { id: 'mesopotamia', label: 'Mesopotamia', theme: 'mesopotamia', start: -4000, end: -539, regions: [[38, 29, 50, 38]], priority: 30, swatch: ['#efdcc0', '#2e6f8e'] },
  { id: 'egypt', label: 'Ancient Egypt', theme: 'egypt', start: -3150, end: -30, regions: [[24, 21, 37, 32]], priority: 30, swatch: ['#f4e4c1', '#1e5b8a'] },
  { id: 'greece', label: 'Classical Greece', theme: 'greece', start: -800, end: -147, regions: [[19, 34.5, 29, 41.5]], priority: 35, swatch: ['#f7f5ef', '#1d5fa0'] },
  { id: 'rome', label: 'Rome', theme: 'rome', start: -509, end: 476, regions: [[6, 36, 19, 47.5]], priority: 40, swatch: ['#f5f1e8', '#7b1e2b'] },
  { id: 'roman-world', label: 'The Roman World', theme: 'rome', start: -146, end: 476, regions: [[-10, 30, 42, 52], [24, 22, 37, 31]], priority: 20, swatch: ['#f5f1e8', '#7b1e2b'] },
  { id: 'imperial-china', label: 'Imperial China', theme: 'imperial-china', start: -221, end: 1911, regions: [[97, 18, 125, 42]], priority: 25, swatch: ['#f6efe2', '#b22a1e'] },
  { id: 'byzantium', label: 'Byzantium', theme: 'byzantium', start: 477, end: 1453, regions: [[19, 35, 32, 45], [26, 36, 42, 42.5]], priority: 35, swatch: ['#f3ecdf', '#5b2a6e'] },
  { id: 'islamic-golden-age', label: 'The Islamic Golden Age', theme: 'islamic-golden-age', start: 632, end: 1258, regions: [[34, 12, 62, 40], [-10, 35, 0, 44]], priority: 30, swatch: ['#f2ecdc', '#0f6f6a'] },
  { id: 'viking-age', label: 'The Viking Age', theme: 'viking-age', start: 793, end: 1066, regions: [[4, 54, 32, 71], [-25, 62, -12, 67]], priority: 30, swatch: ['#e9ecee', '#3a5f7d'] },
  { id: 'mexica', label: 'The Mexica World', theme: 'mexica', start: 1300, end: 1521, regions: [[-105, 14, -86, 23]], priority: 30, swatch: ['#f3e9d6', '#1f7a6e'] },
  { id: 'edo-japan', label: 'Edo Japan', theme: 'edo-japan', start: 1603, end: 1868, regions: [[129, 30, 146, 46]], priority: 30, swatch: ['#f4efe4', '#2c3e6b'] },
  { id: 'victorian', label: 'Victorian Britain', theme: 'victorian', start: 1837, end: 1901, regions: [[-11, 49.5, 2.5, 61]], priority: 30, swatch: ['#f1ebdf', '#5e1f2a'] },
];

export const ERA_ENTRIES: EraEntry[] = [...GLOBAL_ERAS, ...REGIONAL_ERAS];

/** Regional eras apply only when the visible map is at most this wide (degrees). */
export const REGIONAL_MAX_SPAN = 60;

export function boxArea([w, s, e, n]: Box): number {
  return Math.max(0, e - w) * Math.max(0, n - s);
}
