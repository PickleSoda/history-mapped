import type { EraTheme } from '@/lib/era/types';

/**
 * Era theme modules, one chunk each: a theme's palette, map styling and the
 * loader for its font ship only when that era first becomes active.
 */
const modules = import.meta.glob<{ default: EraTheme }>('./themes/*.ts');

const cache = new Map<string, Promise<EraTheme>>();

export const THEME_IDS = Object.keys(modules).map((path) => path.replace(/^\.\/themes\/|\.ts$/g, ''));

export function loadEraTheme(id: string): Promise<EraTheme> {
  let theme = cache.get(id);
  if (!theme) {
    const load = modules[`./themes/${id}.ts`];
    if (!load) return Promise.reject(new Error(`no era theme "${id}"`));
    theme = load().then((m) => m.default);
    // A failed chunk load is dropped so the next activation retries.
    theme.catch(() => cache.delete(id));
    cache.set(id, theme);
  }
  return theme;
}
