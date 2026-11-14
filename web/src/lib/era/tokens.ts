import { mix, withContrast } from '@/lib/era/color';
import type { EraTheme } from '@/lib/era/types';

const WHITE = '#ffffff';
const BLACK = '#000000';

/** Minimum contrast for body text and for secondary text (WCAG AA is 4.5). */
export const TEXT_CONTRAST = 7;
export const MUTED_CONTRAST = 4.6;

export type Tokens = Record<string, string>;

/**
 * The app's design tokens (the shadcn set in styles.css plus the `--era-*`
 * extras) for one theme in light or dark mode, all derived from its paper,
 * ink and accent colours. Text colours are pushed until they meet the
 * contrast floors above.
 */
export function eraTokens(theme: EraTheme, mode: 'light' | 'dark'): Tokens {
  const accent2 = theme.accent2 ?? theme.accent;
  if (mode === 'light') {
    const bg = theme.paper;
    const fg = withContrast(theme.ink, bg, TEXT_CONTRAST, BLACK);
    const card = mix(bg, WHITE, 0.45);
    const primary = withContrast(mix(theme.accent, theme.ink, 0.15), card, 4.8, theme.ink);
    const muted = mix(bg, theme.ink, 0.05);
    const mutedFg = withContrast(mix(theme.ink, bg, 0.38), muted, MUTED_CONTRAST, theme.ink);
    const accent = mix(bg, theme.accent, 0.12);
    const border = mix(bg, theme.ink, 0.12);
    const ring = mix(theme.accent, bg, 0.45);
    return {
      '--background': bg,
      '--foreground': fg,
      '--card': card,
      '--card-foreground': fg,
      '--popover': card,
      '--popover-foreground': fg,
      '--primary': primary,
      '--primary-foreground': withContrast(card, primary, 4.5, WHITE),
      '--secondary': muted,
      '--secondary-foreground': fg,
      '--muted': muted,
      '--muted-foreground': mutedFg,
      '--accent': accent,
      '--accent-foreground': fg,
      '--border': border,
      '--input': border,
      '--ring': ring,
      '--sidebar': mix(bg, theme.ink, 0.02),
      '--sidebar-foreground': fg,
      '--sidebar-primary': primary,
      '--sidebar-primary-foreground': withContrast(card, primary, 4.5, WHITE),
      '--sidebar-accent': accent,
      '--sidebar-accent-foreground': fg,
      '--sidebar-border': border,
      '--sidebar-ring': ring,
      '--era-accent': theme.accent,
      '--era-accent-2': accent2,
      '--era-ornament': mix(theme.accent, bg, 0.1),
      '--era-tint': theme.accent,
    };
  }

  const bg = theme.night ?? mix(theme.ink, BLACK, 0.35);
  const fg = withContrast(mix(theme.paper, WHITE, 0.6), bg, TEXT_CONTRAST, WHITE);
  const card = mix(bg, theme.paper, 0.06);
  const primary = withContrast(mix(theme.accent, WHITE, 0.4), card, 4.8, WHITE);
  const muted = mix(bg, theme.paper, 0.09);
  const mutedFg = withContrast(mix(theme.paper, bg, 0.4), muted, MUTED_CONTRAST, WHITE);
  const accent = mix(bg, theme.accent, 0.22);
  const border = mix(bg, theme.paper, 0.15);
  const ring = mix(theme.accent, bg, 0.3);
  return {
    '--background': bg,
    '--foreground': fg,
    '--card': card,
    '--card-foreground': fg,
    '--popover': card,
    '--popover-foreground': fg,
    '--primary': primary,
    '--primary-foreground': withContrast(bg, primary, 4.5, BLACK),
    '--secondary': muted,
    '--secondary-foreground': fg,
    '--muted': muted,
    '--muted-foreground': mutedFg,
    '--accent': accent,
    '--accent-foreground': fg,
    '--border': border,
    '--input': mix(bg, theme.paper, 0.2),
    '--ring': ring,
    '--sidebar': mix(bg, theme.paper, 0.035),
    '--sidebar-foreground': fg,
    '--sidebar-primary': primary,
    '--sidebar-primary-foreground': withContrast(bg, primary, 4.5, BLACK),
    '--sidebar-accent': accent,
    '--sidebar-accent-foreground': fg,
    '--sidebar-border': border,
    '--sidebar-ring': ring,
    '--era-accent': mix(theme.accent, WHITE, 0.25),
    '--era-accent-2': mix(accent2, WHITE, 0.25),
    '--era-ornament': mix(theme.accent, WHITE, 0.3),
    '--era-tint': mix(theme.accent, BLACK, 0.2),
  };
}

function block(selector: string, tokens: Tokens, extra: string[] = []): string {
  const lines = Object.entries(tokens).map(([k, v]) => `  ${k}: ${v};`);
  return `${selector} {\n${[...lines, ...extra].join('\n')}\n}`;
}

/**
 * The stylesheet for one theme: its tokens under `html[data-era-theme=…]`,
 * dark ones under `html.dark[data-era-theme=…]` (both outrank the defaults
 * in styles.css), plus its heading font.
 */
export function themeCss(theme: EraTheme, borderUrl?: string): string {
  const sel = `html[data-era-theme="${theme.id}"]`;
  const extra = [
    theme.font ? `  --era-font-heading: ${theme.font.family};` : '',
    borderUrl ? `  --era-border-image: url("${borderUrl}");` : '',
  ].filter(Boolean);
  return [
    block(sel, eraTokens(theme, 'light'), extra),
    block(`html.dark[data-era-theme="${theme.id}"]`, eraTokens(theme, 'dark')),
  ].join('\n');
}
