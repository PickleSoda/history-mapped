/**
 * Renders a ```mermaid fence to SVG. `mermaid` (and the diagram type it needs)
 * is imported on first use, so it stays out of every chunk but its own.
 */
import type { Theme } from '@/lib/theme';

// Mindmap branches and timeline sections: the muted scale mermaid derives
// from the light palette. Dark mode would derive near-black fills, so both
// themes use this one, with dark text on it.
const SCALE = [
  '#c0b496',
  '#bba886',
  '#ddcc99',
  '#b8c096',
  '#a3c096',
  '#96c09f',
  '#96c0b4',
  '#96b8c0',
  '#b6afcf',
  '#c096b8',
  '#c096a3',
  '#c09f96',
];
const SCALE_VARIABLES = Object.fromEntries(
  SCALE.flatMap((color, i) => [
    [`cScale${i}`, color],
    [`cScaleLabel${i}`, '#2a2722'],
  ]),
);

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
    noteTextColor: '#2a2722',
    ...SCALE_VARIABLES,
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
    noteTextColor: '#faf9f6',
    edgeLabelBackground: '#423d35',
    ...SCALE_VARIABLES,
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
    // The theme derives its other colours (ER table rows among them) from
    // themeVariables.darkMode, not from the top-level flag.
    themeVariables: {
      ...THEME_VARIABLES[theme],
      darkMode: theme === 'dark',
      fontFamily: "'Geist Variable', sans-serif",
    },
    // The docs column is about 700px wide and an SVG shrinks to fit it, so
    // keep diagrams narrow enough to stay legible: wrap sequence messages to
    // the actor width, and tighten the flowchart and ER spacing (leaving a
    // little room under subgraph titles).
    sequence: { wrap: true, width: 120, actorMargin: 30 },
    flowchart: {
      nodeSpacing: 30,
      rankSpacing: 35,
      padding: 8,
      wrappingWidth: 150,
      subGraphTitleMargin: { top: 0, bottom: 10 },
    },
    er: { nodeSpacing: 40, rankSpacing: 50 },
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
