/**
 * Renders a ```mermaid fence to SVG. `mermaid` (and the diagram type it needs)
 * is imported on first use, so it stays out of every chunk but its own.
 */
import type { Theme } from '@/lib/theme';

// Mermaid derives its palette from hex values (no CSS variables): these are
// the site tokens from styles.css.
const THEME_VARIABLES: Record<Theme, Record<string, string>> = {
  light: {
    background: '#faf9f6',
    primaryColor: '#f0ede6',
    primaryTextColor: '#2a2722',
    primaryBorderColor: '#b8ab97',
    secondaryColor: '#e9e3d8',
    tertiaryColor: '#fdfcf9',
    lineColor: '#6f685f',
    textColor: '#2a2722',
    noteBkgColor: '#f6efdd',
    noteBorderColor: '#bd8a2c',
  },
  dark: {
    background: '#2a2722',
    primaryColor: '#3a362f',
    primaryTextColor: '#faf9f6',
    primaryBorderColor: '#6b6252',
    secondaryColor: '#423d35',
    tertiaryColor: '#34302a',
    lineColor: '#a8a094',
    textColor: '#faf9f6',
    noteBkgColor: '#332a14',
    noteBorderColor: '#d9a94e',
  },
};

let sequence = 0;

/** SVG markup for a diagram; throws on a syntax error. */
export async function renderMermaid(code: string, theme: Theme): Promise<string> {
  const { default: mermaid } = await import('mermaid');
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict',
    theme: 'base',
    darkMode: theme === 'dark',
    themeVariables: { ...THEME_VARIABLES[theme], fontFamily: "'Geist Variable', sans-serif" },
  });
  const id = `doc-mermaid-${++sequence}`;
  try {
    const { svg } = await mermaid.render(id, code);
    return svg;
  } finally {
    // A failed render can leave its scratch element behind in <body>.
    document.getElementById(id)?.remove();
    document.getElementById(`d${id}`)?.remove();
  }
}
