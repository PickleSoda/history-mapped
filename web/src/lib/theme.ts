/**
 * Theme (light/dark) source of truth for the Atlas SPA.
 *
 * A zustand store holds the active theme so every consumer — the toggle, the
 * map, the timeline — shares one value. `applyTheme` writes the `.dark` class on
 * <html> (which drives all CSS custom properties) and the browser theme-color.
 * The initial `.dark` class is set pre-paint by an inline script in index.html.
 */
import { create } from 'zustand';

export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'hm-theme';
const THEME_COLOR: Record<Theme, string> = { light: '#faf9f6', dark: '#2a2722' };

function prefersDark(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
  );
}

/** The OS-level preference. */
export function systemTheme(): Theme {
  return prefersDark() ? 'dark' : 'light';
}

/** The user's explicitly-stored choice, or null if they never chose. */
export function storedTheme(): Theme | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return v === 'light' || v === 'dark' ? v : null;
  } catch {
    return null;
  }
}

/** Explicit choice wins; otherwise follow the system. */
export function resolveTheme(): Theme {
  return storedTheme() ?? systemTheme();
}

/** Persist an explicit choice. */
export function storeTheme(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* ignore quota / privacy-mode errors */
  }
}

/** Reflect the theme onto the document (class + browser chrome color). */
export function applyTheme(theme: Theme): void {
  if (typeof document === 'undefined') return;
  document.documentElement.classList.toggle('dark', theme === 'dark');
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', THEME_COLOR[theme]);
}

interface ThemeState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggle: () => void;
}

export const useTheme = create<ThemeState>((set, get) => ({
  theme: resolveTheme(),
  setTheme: (theme) => {
    storeTheme(theme);
    applyTheme(theme);
    set({ theme });
  },
  toggle: () => {
    const next: Theme = get().theme === 'dark' ? 'light' : 'dark';
    storeTheme(next);
    applyTheme(next);
    set({ theme: next });
  },
}));

// Follow the OS preference until the user makes an explicit choice.
if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
  window
    .matchMedia('(prefers-color-scheme: dark)')
    .addEventListener('change', () => {
      if (storedTheme()) return;
      const next = systemTheme();
      applyTheme(next);
      useTheme.setState({ theme: next });
    });
}
