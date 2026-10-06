import type { Core } from 'cytoscape';
import {
  Info,
  Maximize,
  RotateCcw,
  SlidersHorizontal,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useFetchNeighbourhood, useReducedMotion, useSelection } from '@/hooks';
import {
  collapseExpansion,
  computeVisibility,
  createGraphModel,
  groupFacets,
  isFilterActive,
  makeFilter,
  mergeNeighbourhood,
  nodeDiameter,
  typeFacets,
  yearExtent,
} from '@/lib/graph';
import type { GraphFilter, GraphModel } from '@/lib/graph';
import { GROUP_ORDER } from '@/lib/groups';
import type { GraphEdge, GraphNode } from '@/lib/schemas/graph';
import { useTheme } from '@/lib/theme';
import { cn } from '@/lib/utils';
import { frameElements, fullLayout, loadCytoscape, placeNodes } from './cytoscape-loader';
import { buildStylesheet, readPalette } from './graph-style';
import { GraphFilterBar, relLabel } from './GraphFilterBar';
import { EdgeInfoCard, NodeInfoCard } from './GraphInfoCard';
import type { GraphSelection } from './GraphInfoCard';
import { GraphLegend } from './GraphLegend';

export interface RelationGraphProps {
  /** Base graph: an entity neighbourhood, a chronicle graph or a step
   *  subgraph. Pass memoised arrays — a new identity resets expansions,
   *  filters and the layout. */
  nodes: readonly GraphNode[];
  edges: readonly GraphEdge[];
  /** The entity the graph is centred on: drawn ringed, never filtered out,
   *  and the reference for the info card's "relation to …". */
  rootId?: string | null;
  /** Offer Expand / Collapse on nodes (fetches depth-1 neighbourhoods). */
  expandable?: boolean;
  /** Highlight these nodes (and edges; default: edges among them) and fade
   *  everything else, without relayout — e.g. a chronicle step scrubber. */
  highlight?: { nodes: ReadonlySet<string>; edges?: ReadonlySet<string> } | null;
  /** Pan/zoom to frame the highlight whenever it changes (back to the whole
   *  graph when it clears). */
  fitHighlight?: boolean;
  /** Edges drawn heavy — e.g. a chronicle's primary relationships. */
  emphasisedEdges?: ReadonlySet<string>;
  /** Edges whose type label always shows — e.g. a step's primary edge. */
  labelledEdges?: ReadonlySet<string>;
  /** Nodes drawn faint (and their edges) — e.g. entities outside a chronicle. */
  dimmedNodes?: ReadonlySet<string>;
  /** Compact chrome for small inline graphs: filters behind a toggle, smaller
   *  default height, no status line. */
  compact?: boolean;
  /** Starting filter, e.g. `{ external: false }`. Also what Reset returns to. */
  initialFilter?: Partial<GraphFilter>;
  /** Show the "outside the chronicle" chip (chronicle graphs). */
  externalToggle?: boolean;
  /** Controlled external switch: when given it drives the filter's
   *  `external` flag (and replaces the chip), e.g. a step's "+ external". */
  external?: boolean;
  /** Info-card Open. Default: select the entity (pushes `?sel=`). */
  onOpen?: (id: string) => void;
  /** Canvas height (CSS length). */
  height?: number | string;
  /** The base payload hit the server's edge limit. */
  truncated?: boolean;
  /** Accessible name for the canvas. */
  label?: string;
  className?: string;
}

type LayoutRequest = 'full' | { around: string } | null;

/** Max zoom when framing (a layout, a highlight), so a two-node graph or a
 *  one-node step isn't blown up. */
const FRAME_MAX_ZOOM = 1.4;

function nodeClasses(n: GraphNode, model: GraphModel): string {
  const cls = [`g-${n.entity_group}`];
  if (n.id === model.root) cls.push('root');
  if (model.expansions.has(n.id)) cls.push('expanded');
  return cls.join(' ');
}

/** Square icon button for the canvas controls. */
function ControlButton({
  icon: Icon,
  label,
  onClick,
  pressed,
}: {
  icon: LucideIcon;
  label: string;
  onClick: () => void;
  pressed?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-pressed={pressed}
      title={label}
      className={cn(
        'grid size-7 place-items-center text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
        'focus-visible:relative focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-ring',
        pressed && 'bg-muted text-foreground',
      )}
    >
      <Icon size={14} />
    </button>
  );
}

/**
 * Interactive relation graph (cytoscape + fcose, lazy-loaded). Shared by the
 * entity page and the chronicle page.
 *
 * State lives here, not in the URL: the merged graph model (base + user
 * expansions, see lib/graph/model), the client-side filter, and the clicked
 * node/edge. Filters only toggle element visibility; an expansion lays out
 * only the new nodes, around the expanded one, with everything else pinned.
 * Canvas interaction is pointer-first — the relationship list beside it is the
 * accessible equivalent — but every control is a real, focusable button.
 */
export function RelationGraph({
  nodes,
  edges,
  rootId = null,
  expandable = true,
  highlight = null,
  fitHighlight = false,
  emphasisedEdges,
  labelledEdges,
  dimmedNodes,
  compact = false,
  initialFilter,
  externalToggle = false,
  external,
  onOpen,
  height,
  truncated = false,
  label,
  className,
}: RelationGraphProps) {
  const { select } = useSelection();
  const open = onOpen ?? select;
  const fetchNeighbourhood = useFetchNeighbourhood();
  const reducedMotion = useReducedMotion();
  const theme = useTheme((s) => s.theme);

  // ── State: model (base + expansions), filter, selection ──────────────────
  const makeInitialFilter = () =>
    makeFilter(external === undefined ? initialFilter : { ...initialFilter, external });
  const [base, setBase] = useState({ nodes, edges, rootId });
  const [model, setModel] = useState(() => createGraphModel({ nodes, edges }, rootId));
  const [filter, setFilter] = useState(makeInitialFilter);
  const [selected, setSelected] = useState<GraphSelection | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(!compact);
  const [showLegend, setShowLegend] = useState(false);
  const [wheelHint, setWheelHint] = useState(false);

  // A new base payload (another root, depth, chronicle or step) starts over.
  if (base.nodes !== nodes || base.edges !== edges || base.rootId !== rootId) {
    setBase({ nodes, edges, rootId });
    setModel(createGraphModel({ nodes, edges }, rootId));
    setFilter(makeInitialFilter());
    setSelected(null);
    setFailed(null);
  }
  // The controlled external switch flips just that part of the filter.
  const [externalProp, setExternalProp] = useState(external);
  if (external !== externalProp) {
    setExternalProp(external);
    if (external !== undefined) setFilter((f) => ({ ...f, external }));
  }

  const anchors = useMemo(() => {
    const s = new Set<string>();
    for (const n of model.nodes.values()) if (n.in_chronicle) s.add(n.id);
    return s;
  }, [model]);
  const visibility = useMemo(
    () => computeVisibility(model.nodes.values(), model.edges.values(), filter, { root: rootId, anchors }),
    [model, filter, rootId, anchors],
  );
  const types = useMemo(() => typeFacets(model.edges.values()), [model]);
  const groups = useMemo(() => groupFacets(model.nodes.values(), GROUP_ORDER, rootId), [model, rootId]);
  const extent = useMemo(() => yearExtent(model.edges.values()), [model]);

  // ── Cytoscape instance (created once the lazy chunk arrives) ─────────────
  const stageRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [ready, setReady] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const layoutRef = useRef<LayoutRequest>('full');
  const syncedBaseRef = useRef<object | null>(null);
  /** Nodes that have a laid-out position. Hidden nodes are left out of a
   *  layout; when a filter later reveals them they're placed incrementally. */
  const placedRef = useRef(new Set<string>());
  const framedRef = useRef<RelationGraphProps['highlight'] | undefined>(undefined);
  const compactRef = useRef(compact);

  useEffect(() => {
    let cancelled = false;
    let cy: Core | null = null;
    loadCytoscape().then(
      (cytoscape) => {
        if (cancelled || !containerRef.current) return;
        cy = cytoscape({
          container: containerRef.current,
          style: buildStylesheet(readPalette(), { compact: compactRef.current }),
          minZoom: 0.12,
          maxZoom: 3.5,
          boxSelectionEnabled: false,
          selectionType: 'single',
        });
        cy.on('tap', 'node', (e) => setSelected({ kind: 'node', id: e.target.id() }));
        cy.on('tap', 'edge', (e) => setSelected({ kind: 'edge', id: e.target.id() }));
        cy.on('tap', (e) => {
          if (e.target === cy) setSelected(null);
        });
        cy.on('mouseover', 'node', (e) => {
          e.target.addClass('hover');
          e.target.connectedEdges().addClass('labelled');
          if (containerRef.current) containerRef.current.style.cursor = 'pointer';
        });
        cy.on('mouseout', 'node', (e) => {
          e.target.removeClass('hover');
          e.target.connectedEdges().removeClass('labelled');
          if (containerRef.current) containerRef.current.style.cursor = '';
        });
        cy.on('mouseover', 'edge', (e) => e.target.addClass('labelled'));
        cy.on('mouseout', 'edge', (e) => e.target.removeClass('labelled'));
        layoutRef.current = 'full';
        syncedBaseRef.current = null;
        placedRef.current.clear();
        framedRef.current = undefined;
        cyRef.current = cy;
        setReady(true);
      },
      () => {
        if (!cancelled) setLoadFailed(true);
      },
    );
    return () => {
      cancelled = true;
      cy?.destroy();
      cyRef.current = null;
      setReady(false);
    };
  }, []);

  // Keep the canvas sized to its box.
  useEffect(() => {
    const el = containerRef.current;
    if (!ready || !el) return;
    const ro = new ResizeObserver(() => cyRef.current?.resize());
    ro.observe(el);
    return () => ro.disconnect();
  }, [ready]);

  // Plain wheel scrolls the page; Ctrl/⌘ + wheel (and trackpad pinch, which
  // arrives as ctrl+wheel) zooms. Cytoscape listens on its container, so a
  // capture listener on the stage stops plain wheels before they reach it.
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    let t: ReturnType<typeof setTimeout> | undefined;
    const onWheel = (e: WheelEvent) => {
      if (e.ctrlKey || e.metaKey) return;
      e.stopPropagation();
      setWheelHint(true);
      clearTimeout(t);
      t = setTimeout(() => setWheelHint(false), 1400);
    };
    stage.addEventListener('wheel', onWheel, { capture: true, passive: true });
    return () => {
      clearTimeout(t);
      stage.removeEventListener('wheel', onWheel, { capture: true });
    };
  }, []);

  // Theme flips rebuild the stylesheet from the new tokens.
  useEffect(() => {
    compactRef.current = compact;
    cyRef.current?.style(buildStylesheet(readPalette(), { compact }));
  }, [ready, theme, compact]);

  // Model + filter → canvas: add/remove elements, apply visibility, lay out.
  // Layouts only ever run over visible elements; anything visible without a
  // position yet (expansion newcomers, nodes a filter just revealed) is placed
  // incrementally with the rest pinned.
  useEffect(() => {
    const cy = cyRef.current;
    if (!ready || !cy) return;
    const placed = placedRef.current;
    if (syncedBaseRef.current !== base) {
      syncedBaseRef.current = base;
      layoutRef.current = 'full';
    }
    cy.batch(() => {
      cy.elements().forEach((el) => {
        const id = el.id();
        const isNode = el.group() === 'nodes';
        const keep = isNode ? model.nodes.has(id) : model.edges.has(id);
        if (keep) return;
        el.remove();
        if (isNode) placed.delete(id);
      });
      for (const n of model.nodes.values()) {
        const el = cy.getElementById(n.id);
        if (el.empty()) {
          cy.add({
            group: 'nodes',
            data: { id: n.id, label: n.name, size: nodeDiameter(n.impact_score, n.id === model.root) },
            classes: nodeClasses(n, model),
          });
        } else {
          // Toggle only the classes the model owns; `dim` / `faded` / `hover`
          // belong to other effects and must survive a filter change.
          el.toggleClass('root', n.id === model.root);
          el.toggleClass('expanded', model.expansions.has(n.id));
        }
      }
      for (const e of model.edges.values()) {
        if (cy.getElementById(e.id).nonempty()) continue;
        cy.add({
          group: 'edges',
          data: { id: e.id, source: e.source, target: e.target, label: relLabel(e.relationship_type) },
        });
      }
      cy.nodes().forEach((n) => {
        n.toggleClass('hidden', !visibility.nodes.has(n.id()));
      });
      cy.edges().forEach((e) => {
        e.toggleClass('hidden', !visibility.edges.has(e.id()));
      });
    });

    const request = layoutRef.current;
    layoutRef.current = null;
    if (request === 'full') {
      placed.clear();
      fullLayout(cy);
      cy.nodes(':visible').forEach((n) => {
        placed.add(n.id());
      });
      frameElements(cy, cy.elements(':visible'), { animate: false, maxZoom: FRAME_MAX_ZOOM, padding: 28 });
      return;
    }
    const fresh = cy
      .nodes(':visible')
      .filter((n) => !placed.has(n.id()))
      .map((n) => n.id());
    if (fresh.length === 0) return;
    fresh.forEach((id) => placed.add(id));
    placeNodes(cy, fresh, {
      around: request?.around ?? null,
      animate: !reducedMotion,
      onDone: () => {
        // Bring the newcomers into view if they landed off-screen.
        const ids = new Set(fresh);
        const landed = cy.nodes(':visible').filter((n) => ids.has(n.id()));
        if (landed.empty()) return;
        const bb = landed.boundingBox();
        const ext = cy.extent();
        if (bb.x1 < ext.x1 || bb.x2 > ext.x2 || bb.y1 < ext.y1 || bb.y2 > ext.y2) {
          if (reducedMotion) cy.fit(cy.elements(':visible'), 28);
          else cy.animate({ fit: { eles: cy.elements(':visible'), padding: 28 } }, { duration: 300 });
        }
      },
    });
  }, [ready, base, model, visibility, reducedMotion]);

  // Highlight / emphasis / dimming — class toggles only, no relayout.
  useEffect(() => {
    const cy = cyRef.current;
    if (!ready || !cy) return;
    cy.batch(() => {
      cy.nodes().forEach((n) => {
        n.toggleClass('dim', dimmedNodes?.has(n.id()) ?? false);
        n.toggleClass('faded', highlight != null && !highlight.nodes.has(n.id()));
      });
      cy.edges().forEach((e) => {
        const id = e.id();
        const src = e.data('source') as string;
        const tgt = e.data('target') as string;
        e.toggleClass('emph', emphasisedEdges?.has(id) ?? false);
        e.toggleClass('tagged', labelledEdges?.has(id) ?? false);
        e.toggleClass('dim', (dimmedNodes?.has(src) || dimmedNodes?.has(tgt)) ?? false);
        const lit = !highlight
          ? true
          : highlight.edges
            ? highlight.edges.has(id)
            : highlight.nodes.has(src) && highlight.nodes.has(tgt);
        e.toggleClass('faded', !lit);
      });
    });
  }, [ready, model, highlight, emphasisedEdges, labelledEdges, dimmedNodes]);

  // Frame the highlight when it changes (only then — not on expansions).
  useEffect(() => {
    const cy = cyRef.current;
    if (!ready || !cy || !fitHighlight || framedRef.current === highlight) return;
    const first = framedRef.current === undefined;
    framedRef.current = highlight;
    if (!highlight) {
      if (!first) frameElements(cy, cy.elements(':visible'), { animate: !reducedMotion, maxZoom: cy.maxZoom() });
      return;
    }
    const eles = cy.nodes(':visible').filter((n) => highlight.nodes.has(n.id()));
    if (eles.empty()) return;
    frameElements(cy, eles, { animate: !reducedMotion && !first, maxZoom: FRAME_MAX_ZOOM });
  }, [ready, highlight, fitHighlight, reducedMotion, visibility]);

  // The info card's subject, dropped if it was removed or filtered away.
  const active =
    selected &&
    (selected.kind === 'node' ? visibility.nodes : visibility.edges).has(selected.id)
      ? selected
      : null;

  // Mirror the card's subject onto the canvas selection + labelled edges.
  useEffect(() => {
    const cy = cyRef.current;
    if (!ready || !cy) return;
    cy.batch(() => {
      cy.elements(':selected').unselect();
      cy.edges('.pinned').removeClass('pinned');
      if (!active) return;
      const el = cy.getElementById(active.id);
      el.select();
      if (active.kind === 'node') el.connectedEdges().addClass('pinned');
    });
  }, [ready, active, model]);

  // ── Actions ──────────────────────────────────────────────────────────────
  const expand = async (id: string) => {
    setBusy(id);
    setFailed(null);
    try {
      const hood = await fetchNeighbourhood(id);
      layoutRef.current = { around: id };
      setModel((m) => mergeNeighbourhood(m, id, hood).model);
    } catch {
      setFailed(id);
    } finally {
      setBusy(null);
    }
  };
  const collapse = (id: string) => setModel((m) => collapseExpansion(m, id).model);

  const fit = () => {
    const cy = cyRef.current;
    if (!cy) return;
    const eles = cy.elements(':visible');
    if (reducedMotion) cy.fit(eles, 28);
    else cy.animate({ fit: { eles, padding: 28 } }, { duration: 300 });
  };
  const zoomBy = (factor: number) => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.zoom({
      level: cy.zoom() * factor,
      renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
    });
  };
  const reset = () => {
    layoutRef.current = 'full';
    setModel(createGraphModel({ nodes, edges }, rootId));
    setFilter(makeInitialFilter());
    setSelected(null);
    setFailed(null);
  };

  const filtered = isFilterActive(filter);
  const stageHeight = height ?? (compact ? 300 : 'min(64vh, 560px)');
  const total = { nodes: model.nodes.size, edges: model.edges.size };
  const shown = { nodes: visibility.nodes.size, edges: visibility.edges.size };
  const node = active?.kind === 'node' ? model.nodes.get(active.id) : undefined;
  const edge = active?.kind === 'edge' ? model.edges.get(active.id) : undefined;
  const ariaLabel =
    label ?? `Relation graph: ${shown.nodes} entities and ${shown.edges} relations shown`;

  return (
    <div className={cn('flex flex-col gap-2.5', className)}>
      {showFilters && (
        <GraphFilterBar
          filter={filter}
          onChange={setFilter}
          types={types}
          groups={groups}
          extent={extent}
          externalToggle={externalToggle && external === undefined}
        />
      )}

      <div
        ref={stageRef}
        data-vaul-no-drag
        className="relative overflow-hidden rounded-xl border bg-card"
        style={{
          height: stageHeight,
          backgroundImage: 'radial-gradient(var(--border) 1px, transparent 1px)',
          backgroundSize: '18px 18px',
        }}
      >
        {/* Cytoscape forces `position: relative` on its container, so size it
            by width/height rather than absolute insets. */}
        <div ref={containerRef} role="img" aria-label={ariaLabel} className="h-full w-full" />

        {!ready && !loadFailed && (
          <div className="absolute inset-0 grid place-items-center text-[12px] text-muted-foreground">
            <span className="animate-pulse motion-reduce:animate-none">Drawing the graph…</span>
          </div>
        )}
        {loadFailed && (
          <div className="absolute inset-0 grid place-items-center px-6 text-center text-[12px] text-destructive">
            The graph couldn’t load. The relationship list below has the same data.
          </div>
        )}

        {/* Canvas controls, top-left like the map's. */}
        <div className="absolute left-2 top-2 flex flex-col overflow-hidden rounded-lg border bg-card/95 shadow-sm backdrop-blur">
          <ControlButton icon={ZoomIn} label="Zoom in" onClick={() => zoomBy(1.3)} />
          <ControlButton icon={ZoomOut} label="Zoom out" onClick={() => zoomBy(1 / 1.3)} />
          <ControlButton icon={Maximize} label="Fit to view" onClick={fit} />
          <ControlButton icon={RotateCcw} label="Reset graph" onClick={reset} />
          {compact && (
            <ControlButton
              icon={SlidersHorizontal}
              label={showFilters ? 'Hide filters' : 'Show filters'}
              pressed={showFilters}
              onClick={() => setShowFilters((v) => !v)}
            />
          )}
          <ControlButton
            icon={Info}
            label={showLegend ? 'Hide legend' : 'Show legend'}
            pressed={showLegend}
            onClick={() => setShowLegend((v) => !v)}
          />
        </div>

        {showLegend && (
          <div className="pointer-events-none absolute bottom-2 left-2">
            <GraphLegend dimmed={dimmedNodes != null && dimmedNodes.size > 0} />
          </div>
        )}

        {(node || edge) && (
          <div className="pointer-events-none absolute right-2 top-2 flex max-h-full justify-end">
            {node ? (
              <NodeInfoCard
                node={node}
                model={model}
                rootId={rootId}
                visibleEdges={visibility.edges}
                expandable={expandable}
                busy={busy === node.id}
                failed={failed === node.id}
                onOpen={() => open(node.id)}
                onExpand={() => void expand(node.id)}
                onCollapse={() => collapse(node.id)}
                onClose={() => setSelected(null)}
              />
            ) : (
              edge && (
                <EdgeInfoCard
                  edge={edge}
                  model={model}
                  onSelectNode={(id) => setSelected({ kind: 'node', id })}
                  onClose={() => setSelected(null)}
                />
              )
            )}
          </div>
        )}

        <div
          aria-hidden
          className={cn(
            'pointer-events-none absolute bottom-2 left-1/2 -translate-x-1/2 rounded-full bg-foreground/80 px-2.5 py-1 text-[11px] text-background transition-opacity duration-300 motion-reduce:transition-none',
            wheelHint ? 'opacity-100' : 'opacity-0',
          )}
        >
          Hold Ctrl/⌘ to zoom
        </div>
      </div>

      {!compact && (
        <p className="flex flex-wrap gap-x-3 font-mono text-[10px] text-muted-foreground" aria-live="polite">
          <span>
            {filtered ? `${shown.nodes} of ${total.nodes}` : total.nodes} entities ·{' '}
            {filtered ? `${shown.edges} of ${total.edges}` : total.edges} relations
          </span>
          {model.expansions.size > 0 && <span>{model.expansions.size} expanded</span>}
          {truncated && <span>capped to the strongest relations</span>}
        </p>
      )}
    </div>
  );
}
