/**
 * Lazy cytoscape + fcose. The graph library is ~0.5 MB, so it is never in the
 * atlas entry chunk: the first RelationGraph to mount pulls it in with a
 * dynamic import, and every later graph reuses the same promise.
 */
import type cytoscape from 'cytoscape';
import type { Core, EdgeSingular, LayoutOptions, NodeSingular } from 'cytoscape';

type Cytoscape = typeof cytoscape;

let loading: Promise<Cytoscape> | null = null;

export function loadCytoscape(): Promise<Cytoscape> {
  loading ??= Promise.all([import('cytoscape'), import('cytoscape-fcose')]).then(
    ([cy, fcose]) => {
      cy.default.use(fcose.default);
      return cy.default;
    },
    (err) => {
      loading = null; // let a remount retry after a failed chunk load
      throw err;
    },
  );
  return loading;
}

/** The fcose options we use (the extension's types aren't published). */
interface FcoseOptions {
  name: 'fcose';
  quality?: 'draft' | 'default' | 'proof';
  randomize?: boolean;
  animate?: boolean;
  animationDuration?: number;
  animationEasing?: string;
  fit?: boolean;
  padding?: number;
  nodeDimensionsIncludeLabels?: boolean;
  packComponents?: boolean;
  nodeRepulsion?: number | ((node: NodeSingular) => number);
  idealEdgeLength?: number | ((edge: EdgeSingular) => number);
  edgeElasticity?: number;
  gravity?: number;
  gravityRange?: number;
  numIter?: number;
  nodeSeparation?: number;
  tile?: boolean;
  fixedNodeConstraint?: { nodeId: string; position: { x: number; y: number } }[];
  stop?: () => void;
}

const BASE_LAYOUT: Omit<FcoseOptions, 'randomize' | 'animate'> = {
  name: 'fcose',
  quality: 'default',
  padding: 28,
  nodeDimensionsIncludeLabels: false,
  packComponents: true,
  nodeRepulsion: 16000,
  // Hubs get longer spokes so a 150-leaf star spreads into rings instead of
  // a clump; edges between minor nodes stay short.
  idealEdgeLength: (edge: EdgeSingular) =>
    55 + 7 * Math.sqrt(Math.max(edge.source().degree(false), edge.target().degree(false))),
  edgeElasticity: 0.4,
  gravity: 0.3,
  gravityRange: 3.2,
  numIter: 2500,
  nodeSeparation: 70,
  tile: true,
};

/** Full layout from scratch (first render / reset). Never animated — the
 *  graph simply appears laid out. */
export function fullLayout(cy: Core): void {
  cy.layout({ ...BASE_LAYOUT, randomize: true, animate: false, fit: true } as unknown as LayoutOptions).run();
}

/**
 * Place `added` nodes without disturbing the rest: each starts next to the
 * node it hangs off — on a ring around `around` (the expanded node) when
 * given, else beside its already-placed neighbours — then fcose settles only
 * the newcomers while every other visible node is pinned where it is.
 */
export function placeNodes(
  cy: Core,
  added: string[],
  opts: { around: string | null; animate: boolean; onDone?: () => void },
): void {
  const fresh = new Set(added);
  const centre = opts.around ? cy.getElementById(opts.around) : null;
  const hub = centre && centre.nonempty() && centre.visible() ? centre.position() : null;
  const r = 70 + Math.min(110, added.length * 4);
  const bb = cy.nodes(':visible').filter((n) => !fresh.has(n.id())).boundingBox();
  const middle = Number.isFinite(bb.x1) ? { x: (bb.x1 + bb.x2) / 2, y: (bb.y1 + bb.y2) / 2 } : { x: 0, y: 0 };
  added.forEach((id, i) => {
    const node = cy.getElementById(id);
    const a = (2 * Math.PI * i) / added.length;
    if (hub) {
      node.position({ x: hub.x + r * Math.cos(a), y: hub.y + r * Math.sin(a) });
      return;
    }
    let sx = 0;
    let sy = 0;
    let k = 0;
    node.neighborhood('node:visible').forEach((n) => {
      if (fresh.has(n.id())) return;
      const p = n.position();
      sx += p.x;
      sy += p.y;
      k++;
    });
    const at = k > 0 ? { x: sx / k, y: sy / k } : middle;
    node.position({ x: at.x + 60 * Math.cos(a * 7), y: at.y + 60 * Math.sin(a * 7) });
  });
  const eles = cy.elements(':visible');
  const fixed: { nodeId: string; position: { x: number; y: number } }[] = [];
  let movable = 0;
  eles.nodes().forEach((n) => {
    if (fresh.has(n.id())) movable++;
    else fixed.push({ nodeId: n.id(), position: { ...n.position() } });
  });
  if (movable === 0) {
    opts.onDone?.();
    return;
  }
  const layout = eles.layout({
    ...BASE_LAYOUT,
    randomize: false,
    fit: false,
    animate: opts.animate,
    animationDuration: 450,
    animationEasing: 'ease-out-cubic',
    fixedNodeConstraint: fixed,
  } as unknown as LayoutOptions);
  if (opts.onDone) layout.one('layoutstop', opts.onDone);
  layout.run();
}

/** Pan/zoom so `eles` fill the canvas, never zooming past `maxZoom`. */
export function frameElements(
  cy: Core,
  eles: ReturnType<Core['elements']>,
  opts: { animate: boolean; maxZoom: number; padding?: number },
): void {
  if (eles.empty()) return;
  const pad = opts.padding ?? 40;
  const bb = eles.boundingBox();
  const w = Math.max(1, cy.width() - 2 * pad);
  const h = Math.max(1, cy.height() - 2 * pad);
  const zoom = Math.max(cy.minZoom(), Math.min(opts.maxZoom, w / Math.max(bb.w, 1), h / Math.max(bb.h, 1)));
  const pan = {
    x: cy.width() / 2 - zoom * (bb.x1 + bb.w / 2),
    y: cy.height() / 2 - zoom * (bb.y1 + bb.h / 2),
  };
  cy.stop(true);
  if (opts.animate) cy.animate({ zoom, pan }, { duration: 350, easing: 'ease-out-cubic' });
  else cy.viewport({ zoom, pan });
}
