import { beforeEach, describe, expect, it, vi } from 'vitest';

const KEY = 'hm-theme';

/** jsdom lacks matchMedia — install a controllable stub. */
function setMatchMedia(dark: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: (query: string) => ({
      matches: dark,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  });
}

beforeEach(() => {
  vi.resetModules();
  localStorage.clear();
  document.documentElement.classList.remove('dark');
  if (!document.querySelector('meta[name="theme-color"]')) {
    const meta = document.createElement('meta');
    meta.setAttribute('name', 'theme-color');
    document.head.appendChild(meta);
  }
  setMatchMedia(false);
});

describe('resolveTheme', () => {
  it('prefers a stored explicit choice over the system preference', async () => {
    setMatchMedia(true); // system says dark
    localStorage.setItem(KEY, 'light');
    const { resolveTheme } = await import('./theme');
    expect(resolveTheme()).toBe('light');
  });

  it('falls back to the system preference when nothing is stored', async () => {
    setMatchMedia(true);
    const { resolveTheme } = await import('./theme');
    expect(resolveTheme()).toBe('dark');
  });
});

describe('applyTheme', () => {
  it('adds the dark class and sets theme-color for dark', async () => {
    const { applyTheme } = await import('./theme');
    applyTheme('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(
      document.querySelector('meta[name="theme-color"]')?.getAttribute('content'),
    ).toBe('#2a2722');
  });

  it('removes the dark class and sets theme-color for light', async () => {
    document.documentElement.classList.add('dark');
    const { applyTheme } = await import('./theme');
    applyTheme('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(
      document.querySelector('meta[name="theme-color"]')?.getAttribute('content'),
    ).toBe('#faf9f6');
  });
});

describe('useTheme store', () => {
  it('toggle flips the theme, applies the class, and persists', async () => {
    setMatchMedia(false); // start light
    const { useTheme } = await import('./theme');
    expect(useTheme.getState().theme).toBe('light');
    useTheme.getState().toggle();
    expect(useTheme.getState().theme).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(localStorage.getItem(KEY)).toBe('dark');
  });
});
