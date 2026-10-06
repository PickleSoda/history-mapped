/**
 * Cytoscape stylesheet built from the live theme tokens. Canvas rendering
 * can't read CSS variables, so the palette is resolved from the document once
 * per theme and the stylesheet is rebuilt when the theme flips.
 */
import type { StylesheetJson } from 'cytoscape';
import { GROUP_ORDER } from '@/lib/groups';
import type { EntityGroup } from '@/types/atlas';

export interface GraphPalette {
  groups: Record<EntityGroup, string>;
  foreground: string;
  muted: string;
  border: string;
  card: string;
  background: string;
  ring: string;
}

const FALLBACK: GraphPalette = {
  groups: {
    polity: '#b4543f',
    place: '#6b7f4a',
    event: '#bd8a2c',
    economy: '#4d6a86',
    culture: '#8a5673',
  },
  foreground: '#2a2722',
  muted: '#6f685f',
  border: '#e6e1d8',
  card: '#fdfcf9',
  background: '#faf9f6',
  ring: '#b8ab97',
};

/** Resolve the theme tokens off <html> (call after the theme class applied). */
export function readPalette(): GraphPalette {
  if (typeof document === 'undefined') return FALLBACK;
  const css = getComputedStyle(document.documentElement);
  const v = (name: string, fb: string) => css.getPropertyValue(name).trim() || fb;
  const groups = {} as Record<EntityGroup, string>;
  for (const g of GROUP_ORDER) groups[g] = v(`--g-${g}`, FALLBACK.groups[g]);
  return {
    groups,
    foreground: v('--foreground', FALLBACK.foreground),
    muted: v('--muted-foreground', FALLBACK.muted),
    border: v('--border', FALLBACK.border),
    card: v('--card', FALLBACK.card),
    background: v('--background', FALLBACK.background),
    ring: v('--ring', FALLBACK.ring),
  };
}

const FONT = '"Geist Variable", ui-sans-serif, system-ui, sans-serif';

/**
 * Classes the component toggles:
 * - nodes: `g-<group>`, `root`, `expanded`, `dim` (external), `hover`
 * - edges: `emph` (heavy line), `tagged` (always labelled), `labelled`
 *   (hover), `pinned` (touching the selected node), `dim`
 * - both:  `hidden` (filtered out), `faded` (outside the highlight set)
 */
export function buildStylesheet(p: GraphPalette, opts: { compact?: boolean } = {}): StylesheetJson {
  const fontSize = opts.compact ? 9 : 10;
  return [
    {
      selector: 'node',
      style: {
        width: 'data(size)',
        height: 'data(size)',
        'background-color': p.muted,
        'border-width': 1.5,
        'border-color': p.card,
        label: 'data(label)',
        color: p.foreground,
        'font-family': FONT,
        'font-size': fontSize,
        'font-weight': 500,
        'text-valign': 'bottom',
        'text-halign': 'center',
        'text-margin-y': 4,
        'text-wrap': 'ellipsis',
        'text-max-width': '120px',
        'text-outline-color': p.background,
        'text-outline-width': 2,
        'text-outline-opacity': 0.9,
        'min-zoomed-font-size': 7,
        'overlay-opacity': 0,
        'transition-property': 'opacity',
        'transition-duration': 150,
      },
    },
    ...GROUP_ORDER.map((g) => ({
      selector: `node.g-${g}`,
      style: { 'background-color': p.groups[g] },
    })),
    {
      selector: 'node.expanded',
      style: { 'border-width': 4, 'border-style': 'double', 'border-color': p.foreground },
    },
    {
      selector: 'node.root',
      style: {
        'border-width': 3,
        'border-color': p.foreground,
        'font-size': fontSize + 2,
        'font-weight': 600,
        'min-zoomed-font-size': 0,
        'z-index': 20,
      },
    },
    { selector: 'node.dim', style: { opacity: 0.4 } },
    {
      selector: 'node:selected, node.hover',
      style: {
        'border-width': 3,
        'border-color': p.ring,
        'min-zoomed-font-size': 0,
        'z-index': 30,
      },
    },
    {
      selector: 'node:selected',
      style: { 'border-color': p.foreground, 'overlay-color': p.foreground, 'overlay-opacity': 0.08, 'overlay-padding': 6 },
    },
    {
      selector: 'edge',
      style: {
        width: 1.25,
        'curve-style': 'bezier',
        'line-color': p.muted,
        'line-opacity': 0.38,
        'target-arrow-shape': 'triangle',
        'target-arrow-color': p.muted,
        'arrow-scale': 0.85,
        label: '',
        color: p.muted,
        'font-family': FONT,
        'font-size': fontSize - 1,
        'text-rotation': 'autorotate',
        'text-background-color': p.card,
        'text-background-opacity': 0.92,
        'text-background-padding': '2px',
        'text-background-shape': 'roundrectangle',
        'overlay-opacity': 0,
        'transition-property': 'opacity, line-color',
        'transition-duration': 150,
      },
    },
    {
      selector: 'edge.labelled, edge.pinned, edge.tagged, edge:selected',
      style: { label: 'data(label)', 'line-opacity': 0.9, 'z-index': 10 },
    },
    {
      selector: 'edge:selected',
      style: {
        width: 2.5,
        'line-color': p.foreground,
        'line-opacity': 1,
        'target-arrow-color': p.foreground,
        color: p.foreground,
      },
    },
    {
      selector: 'edge.emph',
      style: {
        width: 2.4,
        'line-color': p.foreground,
        'line-opacity': 0.85,
        'target-arrow-color': p.foreground,
        color: p.foreground,
        'font-weight': 600,
        'z-index': 15,
      },
    },
    { selector: 'edge.dim', style: { opacity: 0.5 } },
    { selector: '.faded', style: { opacity: 0.12, 'text-opacity': 0 } },
    { selector: '.hidden', style: { display: 'none' } },
  ] as StylesheetJson;
}
