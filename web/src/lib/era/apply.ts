import { mix } from '@/lib/era/color';
import { ornamentUrl, pillarUrl } from '@/lib/era/ornaments';
import { textureUrl } from '@/lib/era/textures';
import { eraTokens, themeCss } from '@/lib/era/tokens';
import type { EraTheme } from '@/lib/era/types';
import { applyTheme, useTheme } from '@/lib/theme';

/**
 * Puts an era theme on the document: its stylesheet (added once per theme),
 * the `data-era-*` attributes on <html> that switch it on, its heading font
 * and its texture. Colours change at once (styles.css eases them); the font
 * and the texture follow when they are ready.
 */
const STYLE_ID = 'era-theme-';

let active: string | null = null;

function root(): HTMLElement | null {
  return typeof document === 'undefined' ? null : document.documentElement;
}

function ensureStylesheet(theme: EraTheme): void {
  if (document.getElementById(STYLE_ID + theme.id)) return;
  const el = document.createElement('style');
  el.id = STYLE_ID + theme.id;
  el.textContent = themeCss(
    theme,
    theme.ornament ? ornamentUrl(theme.ornament) : undefined,
    theme.pillar ? pillarUrl(theme.pillar) : undefined,
  );
  document.head.appendChild(el);
}

function setThemeColor(theme: EraTheme): void {
  const dark = useTheme.getState().theme === 'dark';
  const color = eraTokens(theme, dark ? 'dark' : 'light')['--background'];
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', color);
}

export function activateEraTheme(theme: EraTheme): void {
  const html = root();
  if (!html) return;
  ensureStylesheet(theme);
  active = theme.id;
  html.dataset.eraTheme = theme.id;
  html.toggleAttribute('data-era-ornament', Boolean(theme.ornament));
  html.toggleAttribute('data-era-pillar', Boolean(theme.pillar));
  setThemeColor(theme);

  // Fonts download only when a heading first needs them (font-display: swap).
  void theme.font?.load().catch(() => undefined);

  const texture = theme.texture;
  if (!texture) {
    html.style.removeProperty('--era-texture');
    html.style.removeProperty('--era-texture-dark');
    return;
  }
  // Light mode: the texture's own colour. Dark mode: pale marks, fainter.
  void Promise.all([
    textureUrl(texture.kind, texture.color, texture.ui),
    textureUrl(texture.kind, mix(theme.paper, '#ffffff', 0.4), texture.ui * 0.45),
  ]).then(([light, dark]) => {
    if (active !== theme.id) return;
    if (light) html.style.setProperty('--era-texture', `url("${light}")`);
    if (dark) html.style.setProperty('--era-texture-dark', `url("${dark}")`);
  });
}

export function deactivateEraTheme(): void {
  const html = root();
  if (!html) return;
  active = null;
  delete html.dataset.eraTheme;
  html.removeAttribute('data-era-ornament');
  html.removeAttribute('data-era-pillar');
  html.style.removeProperty('--era-texture');
  html.style.removeProperty('--era-texture-dark');
  applyTheme(useTheme.getState().theme);
}

/** Keep the browser chrome colour in step when light/dark mode flips. */
export function refreshEraThemeColor(theme: EraTheme | null): void {
  if (theme && root()) setThemeColor(theme);
}
