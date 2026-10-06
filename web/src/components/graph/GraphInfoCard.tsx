import { ArrowUpRight, Loader2, Minus, MoveRight, Plus, X } from 'lucide-react';
import type { ReactNode } from 'react';
import { GroupDot, TypeBadge } from '@/components/atlas/GroupBadge';
import { formatYear } from '@/lib/format';
import { edgesBetween, shortestPath } from '@/lib/graph';
import type { GraphModel, PathStep } from '@/lib/graph';
import type { GraphEdge, GraphNode } from '@/lib/schemas/graph';
import { relLabel } from './GraphFilterBar';

export type GraphSelection = { kind: 'node'; id: string } | { kind: 'edge'; id: string };

function span(start: number | null, end: number | null): string | null {
  if (start == null && end == null) return null;
  if (start != null && end != null && start !== end) return `${formatYear(start)} – ${formatYear(end)}`;
  return formatYear((start ?? end) as number);
}

function NodeName({ node }: { node: GraphNode | undefined }) {
  if (!node) return <span className="text-muted-foreground">—</span>;
  return (
    <span className="inline-flex min-w-0 items-center gap-1">
      <GroupDot group={node.entity_group} />
      <span className="truncate">{node.name}</span>
    </span>
  );
}

/** "A —type→ B", oriented the way the relationship actually points. */
function EdgeLine({ edge, nodes }: { edge: GraphEdge; nodes: GraphModel['nodes'] }) {
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[12px]">
      <NodeName node={nodes.get(edge.source)} />
      <span className="inline-flex flex-none items-center gap-0.5 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
        {relLabel(edge.relationship_type)} <MoveRight size={11} />
      </span>
      <NodeName node={nodes.get(edge.target)} />
    </div>
  );
}

/** A multi-hop chain from the root: each hop's edge, in walking order. */
function PathChain({ path, nodes }: { path: PathStep[]; nodes: GraphModel['nodes'] }) {
  const shown = path.slice(0, 4);
  return (
    <ol className="space-y-1">
      {shown.map((s) => (
        <li key={s.edge.id}>
          <EdgeLine edge={s.edge} nodes={nodes} />
        </li>
      ))}
      {path.length > shown.length && (
        <li className="text-[11px] text-muted-foreground">… {path.length - shown.length} more hops</li>
      )}
    </ol>
  );
}

function CardShell({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  return (
    <div
      role="dialog"
      aria-label="Graph item"
      onKeyDown={(e) => e.key === 'Escape' && onClose()}
      className="pointer-events-auto max-h-[calc(100%-1rem)] w-[min(19rem,calc(100%-1rem))] overflow-y-auto rounded-xl border bg-popover/95 p-3 text-popover-foreground shadow-lg backdrop-blur"
    >
      <div className="float-right -mr-1 -mt-1 ml-2">
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="grid size-6 place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <X size={14} />
        </button>
      </div>
      {children}
    </div>
  );
}

const sectionLabel = 'mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground';

/** Info card for a clicked node: identity, its relation to the root, and the
 *  Open / Expand / Collapse actions. */
export function NodeInfoCard({
  node,
  model,
  rootId,
  visibleEdges,
  expandable,
  busy,
  failed,
  onOpen,
  onExpand,
  onCollapse,
  onClose,
}: {
  node: GraphNode;
  model: GraphModel;
  rootId: string | null;
  visibleEdges: ReadonlySet<string>;
  expandable: boolean;
  busy: boolean;
  failed: boolean;
  onOpen: () => void;
  onExpand: () => void;
  onCollapse: () => void;
  onClose: () => void;
}) {
  const isRoot = node.id === rootId;
  const expanded = model.expansions.get(node.id);
  const root = rootId ? model.nodes.get(rootId) : undefined;
  const direct = rootId && !isRoot ? edgesBetween(model.edges.values(), rootId, node.id) : [];
  const path =
    rootId && !isRoot && direct.length === 0
      ? shortestPath(model.edges.values(), rootId, node.id, visibleEdges)
      : null;
  let degree = 0;
  for (const e of model.edges.values()) {
    if (visibleEdges.has(e.id) && (e.source === node.id || e.target === node.id)) degree++;
  }
  const years = span(node.start_year, node.end_year);

  return (
    <CardShell onClose={onClose}>
      <TypeBadge group={node.entity_group} type={node.entity_type} />
      <h3 className="mt-2 font-heading text-[15px] font-semibold leading-snug">{node.name}</h3>
      <p className="mt-1 flex flex-wrap gap-x-2 font-mono text-[10px] text-muted-foreground">
        {years && <span>{years}</span>}
        {node.impact_score != null && <span>impact {node.impact_score}</span>}
        <span>
          {degree} relation{degree === 1 ? '' : 's'} in view
        </span>
      </p>

      {rootId && !isRoot && (
        <div className="mt-3 border-t pt-2.5">
          <p className={sectionLabel}>Relation to {root?.name ?? 'the centre'}</p>
          {direct.length > 0 ? (
            <ul className="space-y-1.5">
              {direct.map((e) => (
                <li key={e.id}>
                  <EdgeLine edge={e} nodes={model.nodes} />
                  {e.description && (
                    <p className="mt-0.5 text-[11px] leading-snug text-foreground/70">{e.description}</p>
                  )}
                </li>
              ))}
            </ul>
          ) : path ? (
            <PathChain path={path} nodes={model.nodes} />
          ) : (
            <p className="text-[12px] text-muted-foreground">Not connected in the current view.</p>
          )}
        </div>
      )}
      {isRoot && (
        <p className="mt-3 border-t pt-2.5 text-[12px] text-muted-foreground">
          The centre of this graph.
        </p>
      )}
      {expanded?.truncated && (
        <p className="mt-2 text-[11px] text-muted-foreground">
          Its neighbourhood was capped to the strongest relations.
        </p>
      )}
      {failed && (
        <p className="mt-2 text-[11px] text-destructive">Couldn’t load its relations.</p>
      )}

      <div className="mt-3 flex gap-1.5">
        <button
          type="button"
          onClick={onOpen}
          className="inline-flex h-7 flex-1 items-center justify-center gap-1 rounded-lg bg-primary px-2.5 text-[12px] font-medium text-primary-foreground hover:opacity-90"
        >
          <ArrowUpRight size={14} /> Open
        </button>
        {expandable && !isRoot && (
          <button
            type="button"
            onClick={expanded ? onCollapse : onExpand}
            disabled={busy}
            aria-busy={busy}
            className="inline-flex h-7 flex-1 items-center justify-center gap-1 rounded-lg border bg-card px-2.5 text-[12px] font-medium hover:bg-muted disabled:opacity-60"
          >
            {busy ? (
              <Loader2 size={14} className="animate-spin motion-reduce:animate-none" />
            ) : expanded ? (
              <Minus size={14} />
            ) : (
              <Plus size={14} />
            )}
            {expanded ? 'Collapse' : 'Expand'}
          </button>
        )}
      </div>
    </CardShell>
  );
}

/** Info card for a clicked edge: the relationship, its window and evidence. */
export function EdgeInfoCard({
  edge,
  model,
  onSelectNode,
  onClose,
}: {
  edge: GraphEdge;
  model: GraphModel;
  onSelectNode: (id: string) => void;
  onClose: () => void;
}) {
  const years = span(edge.start_year, edge.end_year);
  const end = (id: string) => (
    <button
      type="button"
      onClick={() => onSelectNode(id)}
      className="min-w-0 rounded-md px-1 py-0.5 text-left hover:bg-muted"
    >
      <NodeName node={model.nodes.get(id)} />
    </button>
  );
  return (
    <CardShell onClose={onClose}>
      <p className={sectionLabel}>Relationship</p>
      <div className="flex flex-col items-start gap-0.5 text-[13px]">
        {end(edge.source)}
        <span className="inline-flex items-center gap-1 pl-1 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          {relLabel(edge.relationship_type)} <MoveRight size={11} />
        </span>
        {end(edge.target)}
      </div>
      <p className="mt-2 flex flex-wrap gap-x-2 font-mono text-[10px] text-muted-foreground">
        {years && <span>{years}</span>}
        {edge.confidence && <span>confidence {edge.confidence}</span>}
        {edge.scope && <span>{edge.scope}</span>}
      </p>
      {edge.description && (
        <p className="mt-2 text-[12px] leading-relaxed text-foreground/80">{edge.description}</p>
      )}
    </CardShell>
  );
}
