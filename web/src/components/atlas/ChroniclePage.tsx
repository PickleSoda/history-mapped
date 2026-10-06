import {
  ChevronLeft,
  ChevronRight,
  Crosshair,
  ExternalLink,
  Layers,
  Route,
} from 'lucide-react';
import { memo, useCallback, useMemo, useRef, useState } from 'react';
import { WhatChanged } from '@/components/atlas/ChroniclePlayer';
import {
  ImpactMeter,
  PageFrame,
  PageSkeleton,
  PageTitle,
  Section,
  Stat,
  StatGrid,
  usePageVariant,
  useScrollRoot,
} from '@/components/atlas/page-kit';
import type { PageVariant } from '@/components/atlas/page-kit';
import { RelationGraph } from '@/components/graph';
import {
  useChronicle,
  useChronicleGraph,
  useChronicleNav,
  useFullPage,
  useNearViewport,
  useReducedMotion,
} from '@/hooks';
import {
  clampStep,
  defaultShowExternal,
  sourceTypeLabel,
  stepRows,
  yearSpanText,
} from '@/lib/chronicle-page';
import type { StepRow } from '@/lib/chronicle-page';
import { humanise, spanText } from '@/lib/entity-format';
import { formatYear } from '@/lib/format';
import { externalNodeIds, stepHighlight, stepSubgraph } from '@/lib/graph';
import type { Chronicle } from '@/lib/schemas/chronicle';
import type { ChronicleGraph } from '@/lib/schemas/graph';
import { cn } from '@/lib/utils';

const ACCENT = 'var(--foreground)';
const isUrl = (s: string) => /^https?:\/\/\S+$/i.test(s.trim());

// ── Header ─────────────────────────────────────────────────────────────────

function Hero({ chronicle, graph }: { chronicle: Chronicle; graph: ChronicleGraph | undefined }) {
  const span = yearSpanText(chronicle.start_year, chronicle.end_year);
  const years = spanText(chronicle.start_year, chronicle.end_year);
  const source = sourceTypeLabel(chronicle.source_type);
  const members = graph?.nodes.filter((n) => n.in_chronicle).length;
  const relations = graph?.edges.filter((e) => e.scope !== 'external').length;
  return (
    <header className="pt-8">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="inline-flex h-[21px] items-center gap-1 rounded-full bg-foreground px-2 text-[11px] font-medium text-background">
          <Route size={12} /> Chronicle
        </span>
        {source && (
          <span className="inline-flex h-[21px] items-center rounded-full border px-2 text-[11px] text-muted-foreground">
            {source}
          </span>
        )}
        {chronicle.status && chronicle.status !== 'published' && (
          <span className="inline-flex h-[21px] items-center rounded-full border border-dashed px-2 text-[11px] capitalize text-muted-foreground">
            {chronicle.status}
          </span>
        )}
      </div>
      <PageTitle>{chronicle.title}</PageTitle>
      <p className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[12.5px] text-foreground/80">
        {span && <span>{span}</span>}
        {years && <span className="text-muted-foreground">{years}</span>}
        <span className="text-muted-foreground">{chronicle.entries.length} steps</span>
      </p>

      <StatGrid>
        <Stat label="Began">{chronicle.start_year != null ? formatYear(chronicle.start_year) : '—'}</Stat>
        <Stat label="Ended">{chronicle.end_year != null ? formatYear(chronicle.end_year) : '—'}</Stat>
        <Stat label="Steps">{chronicle.entries.length}</Stat>
        <Stat label="Entities">{members ?? '…'}</Stat>
        <Stat label="Relations">{relations ?? '…'}</Stat>
        <Stat label="Impact">
          {chronicle.impact_score != null ? (
            <ImpactMeter value={chronicle.impact_score} color={ACCENT} />
          ) : (
            '—'
          )}
        </Stat>
      </StatGrid>
    </header>
  );
}

// ── Whole-chronicle graph + step scrubber ──────────────────────────────────

function StepScrubber({
  rows,
  focus,
  cursor,
  onChange,
  onShowAll,
  onRead,
}: {
  rows: StepRow[];
  focus: number | null;
  cursor: number;
  onChange: (index: number) => void;
  onShowAll: () => void;
  onRead: (index: number) => void;
}) {
  const total = rows.length;
  const at = focus ?? cursor;
  const row = rows[at];
  const year = row ? yearSpanText(row.entry.start_year, row.entry.end_year) : null;
  const btn =
    'grid size-8 flex-none place-items-center rounded-lg border bg-card text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40';
  return (
    <div className="rounded-xl border bg-card/80 p-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <button
          type="button"
          className={btn}
          aria-label="Previous step"
          disabled={focus != null && at <= 0}
          onClick={() => onChange(focus == null ? at : at - 1)}
        >
          <ChevronLeft size={15} />
        </button>
        <input
          type="range"
          min={0}
          max={Math.max(0, total - 1)}
          value={at}
          onChange={(e) => onChange(Number(e.target.value))}
          aria-label="Highlight a step in the graph"
          aria-valuetext={`Step ${at + 1} of ${total}${year ? `, ${year}` : ''}`}
          className={cn(
            'h-1.5 min-w-[140px] flex-1 cursor-pointer accent-foreground',
            focus == null && 'opacity-50',
          )}
        />
        <button
          type="button"
          className={btn}
          aria-label="Next step"
          disabled={focus != null && at >= total - 1}
          onClick={() => onChange(focus == null ? at : at + 1)}
        >
          <ChevronRight size={15} />
        </button>
        <span className="min-w-[9.5rem] font-mono text-[11px] text-muted-foreground" aria-live="polite">
          {focus == null ? (
            'All steps'
          ) : (
            <>
              Step {at + 1}/{total}
              {year && ` · ${year}`}
            </>
          )}
        </span>
        <button
          type="button"
          aria-pressed={focus == null}
          onClick={onShowAll}
          className={cn(
            'h-7 rounded-full border px-2.5 text-[11px] font-medium transition-colors',
            focus == null ? 'border-transparent bg-foreground text-background' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          Show all
        </button>
      </div>
      {focus != null && row?.entry.narrative_text && (
        <p className="mt-2.5 flex gap-2 border-t pt-2.5 text-[13px] leading-snug text-foreground/85">
          <span className="line-clamp-2 flex-1">{row.entry.narrative_text}</span>
          <button
            type="button"
            onClick={() => onRead(at)}
            className="flex-none self-end text-[11px] text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            Read step
          </button>
        </p>
      )}
    </div>
  );
}

function WholeGraph({
  graph,
  rows,
  focus,
  cursor,
  setFocus,
  onRead,
  sectionRef,
}: {
  graph: ChronicleGraph;
  rows: StepRow[];
  focus: number | null;
  cursor: number;
  setFocus: (index: number | null) => void;
  onRead: (index: number) => void;
  sectionRef: React.Ref<HTMLDivElement>;
}) {
  const variant = usePageVariant();
  const externals = useMemo(() => externalNodeIds(graph), [graph]);
  const primaries = useMemo(
    () => new Set(graph.edges.filter((e) => e.scope === 'primary').map((e) => e.id)),
    [graph],
  );
  const initialFilter = useMemo(() => ({ external: defaultShowExternal(graph) }), [graph]);
  const focusRow = focus != null ? rows[focus] : undefined;
  const highlight = useMemo(
    () => (focusRow ? stepHighlight(graph, focusRow.entry.sequence_order) : null),
    [graph, focusRow],
  );
  const labelled = useMemo(
    () => new Set(focusRow?.step?.primary_relationship_id ? [focusRow.step.primary_relationship_id] : []),
    [focusRow],
  );

  return (
    <div ref={sectionRef} className="mt-12 scroll-mt-16">
      <Section title="The whole chronicle">
        <p className="-mt-2 mb-3 text-[12px] text-muted-foreground">
          Every entity in the chronicle and how they relate; the tour’s key relations are drawn heavy.
          Scrub through the steps to light each one up. Entities outside the chronicle are faint.
        </p>
        {graph.nodes.length === 0 ? (
          <p className="text-[13px] text-muted-foreground">No entities are mapped for this chronicle yet.</p>
        ) : (
          <div className="space-y-3">
            <StepScrubber
              rows={rows}
              focus={focus}
              cursor={cursor}
              onChange={(i) => setFocus(clampStep(i, rows.length))}
              onShowAll={() => setFocus(null)}
              onRead={onRead}
            />
            <RelationGraph
              nodes={graph.nodes}
              edges={graph.edges}
              initialFilter={initialFilter}
              externalToggle
              dimmedNodes={externals}
              emphasisedEdges={primaries}
              labelledEdges={labelled}
              highlight={highlight}
              fitHighlight
              height={variant === 'sheet' ? '56dvh' : 'min(70vh, 640px)'}
              label={`Relation graph of the chronicle, ${graph.nodes.length} entities`}
            />
          </div>
        )}
      </Section>
    </div>
  );
}

// ── Step list ──────────────────────────────────────────────────────────────

/** A step's own graph. Mounts its canvas only while the row is near the
 *  viewport (and drops it again when far away), keeping a fixed-height box
 *  in place so the list never jumps. */
function StepGraph({ graph, row, height }: { graph: ChronicleGraph; row: StepRow; height: number }) {
  const boxRef = useRef<HTMLDivElement>(null);
  const near = useNearViewport(boxRef, useScrollRoot(), { near: 300, far: 1200 });
  const [external, setExternal] = useState(false);
  const sub = useMemo(
    () => stepSubgraph(graph, row.entry.sequence_order, { external: true }),
    [graph, row.entry.sequence_order],
  );
  const primary = useMemo(
    () => new Set(sub?.primaryEdgeId ? [sub.primaryEdgeId] : []),
    [sub],
  );
  const extCount = sub?.externalNodeIds.size ?? 0;
  const inStep = sub ? sub.nodes.length - extCount : 0;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="font-mono text-[10px] text-muted-foreground">
          {inStep} entit{inStep === 1 ? 'y' : 'ies'} · {sub ? sub.edges.filter((e) => e.scope !== 'external').length : 0}{' '}
          relations
        </span>
        {extCount > 0 && (
          <button
            type="button"
            aria-pressed={external}
            onClick={() => setExternal((v) => !v)}
            className={cn(
              'inline-flex h-6 items-center gap-1 rounded-full border px-2 text-[11px] transition-colors',
              external
                ? 'border-transparent bg-muted text-foreground'
                : 'border-dashed text-muted-foreground hover:text-foreground',
            )}
            title="Add the outside entities these ones relate to"
          >
            <Layers size={12} /> {external ? 'Hide' : '+'} {extCount} external
          </button>
        )}
      </div>
      <div ref={boxRef} style={{ height }}>
        {!sub || sub.nodes.length === 0 ? (
          <div className="grid h-full place-items-center rounded-xl border border-dashed text-[12px] text-muted-foreground">
            No mapped entities for this step.
          </div>
        ) : near ? (
          <RelationGraph
            nodes={sub.nodes}
            edges={sub.edges}
            compact
            external={external}
            dimmedNodes={sub.externalNodeIds}
            emphasisedEdges={primary}
            labelledEdges={primary}
            height={height}
            label={`Relation graph of step ${row.index + 1}`}
          />
        ) : (
          <div
            aria-hidden
            className="h-full rounded-xl border bg-card"
            style={{
              backgroundImage: 'radial-gradient(var(--border) 1px, transparent 1px)',
              backgroundSize: '18px 18px',
            }}
          />
        )}
      </div>
    </div>
  );
}

const StepItem = memo(function StepItem({
  row,
  total,
  graph,
  focused,
  onFocus,
}: {
  row: StepRow;
  total: number;
  graph: ChronicleGraph | undefined;
  focused: boolean;
  onFocus: (index: number) => void;
}) {
  const variant = usePageVariant();
  const { entry, index } = row;
  const year = yearSpanText(entry.start_year, entry.end_year);
  return (
    <li
      id={`chronicle-step-${index}`}
      className={cn(
        'grid scroll-mt-16 gap-x-10 gap-y-5 border-t py-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]',
        focused && 'border-t-foreground',
      )}
      aria-label={`Step ${index + 1} of ${total}`}
    >
      <div className="min-w-0">
        <div className="flex items-baseline gap-3">
          <span className="font-heading text-[30px] font-semibold leading-none tabular-nums text-muted-foreground/50">
            {index + 1}
          </span>
          {year && <span className="font-mono text-[11px] text-muted-foreground">{year}</span>}
          {focused && (
            <span className="rounded-full bg-foreground px-1.5 py-px text-[10px] font-medium text-background">
              In focus
            </span>
          )}
        </div>
        <p className="mt-3 whitespace-pre-line text-[14px] leading-relaxed text-foreground/90">
          {entry.narrative_text ?? 'No narrative for this step.'}
        </p>
        {entry.primary_relationship && <WhatChanged rel={entry.primary_relationship} />}
        {graph && (
          <button
            type="button"
            onClick={() => onFocus(index)}
            className="mt-4 inline-flex items-center gap-1.5 text-[12px] text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            <Crosshair size={13} /> Focus in the main graph
          </button>
        )}
      </div>
      {graph ? (
        <StepGraph graph={graph} row={row} height={variant === 'sheet' ? 240 : 280} />
      ) : (
        <div className="h-[280px] animate-pulse rounded-xl bg-muted/50 motion-reduce:animate-none" />
      )}
    </li>
  );
});

function About({ chronicle }: { chronicle: Chronicle }) {
  const meta = Object.entries(chronicle.metadata ?? {}).filter(
    ([, v]) => v != null && (typeof v !== 'object' || Array.isArray(v)),
  );
  const ref = chronicle.source_reference?.trim();
  if (!ref && meta.length === 0) return null;
  return (
    <Section title="About this chronicle">
      {ref &&
        (isUrl(ref) ? (
          <a
            href={ref}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-mono text-[12px] underline decoration-border underline-offset-4 hover:decoration-foreground"
          >
            {ref} <ExternalLink size={11} />
          </a>
        ) : (
          <figure>
            <figcaption className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {sourceTypeLabel(chronicle.source_type) ?? 'Source'} excerpt
            </figcaption>
            <blockquote className="whitespace-pre-line border-l-[3px] pl-4 font-heading text-[15px] italic leading-relaxed text-foreground/80">
              {ref}
              {ref.length >= 200 && '…'}
            </blockquote>
          </figure>
        ))}
      {meta.length > 0 && (
        <dl className="mt-5 divide-y divide-dashed rounded-xl border bg-card px-4 text-[13px]">
          {meta.map(([k, v]) => (
            <div key={k} className="flex gap-4 py-2.5">
              <dt className="w-44 flex-none text-muted-foreground">{humanise(k)}</dt>
              <dd className="min-w-0 flex-1 break-words font-mono text-[12px]">
                {k.endsWith('_at') && typeof v === 'string' && !Number.isNaN(Date.parse(v))
                  ? new Date(v).toLocaleString()
                  : Array.isArray(v)
                    ? v.join(', ')
                    : String(v)}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </Section>
  );
}

// ── The page ───────────────────────────────────────────────────────────────

/**
 * The full chronicle page: the tour's header, its whole-chronicle relation
 * graph with a step scrubber, and every step with its own lazily mounted
 * graph. Rendered by the desktop page host and the mobile sheet at full snap.
 * Collapse returns to the tour at the step last in focus.
 */
export function ChroniclePage({ id: slug, variant = 'page' }: { id: string; variant?: PageVariant }) {
  const { data: chronicle, isLoading, isError } = useChronicle(slug);
  const { data: graph, isError: graphError } = useChronicleGraph(slug);
  const { step: urlStep } = useChronicleNav();
  const { collapseChronicle, closeChronicle } = useFullPage();
  const reducedMotion = useReducedMotion();

  const rows = useMemo(() => stepRows(chronicle?.entries ?? [], graph?.steps), [chronicle, graph]);
  // Highlighted step (null = whole graph). Opened mid-tour, start on that step.
  const [focus, setFocusState] = useState<number | null>(urlStep > 0 ? urlStep : null);
  const [cursor, setCursor] = useState(urlStep);
  const setFocus = useCallback((i: number | null) => {
    setFocusState(i);
    if (i != null) setCursor(i);
  }, []);

  const graphRef = useRef<HTMLDivElement>(null);
  const behavior: ScrollBehavior = reducedMotion ? 'auto' : 'smooth';
  const focusInGraph = useCallback(
    (index: number) => {
      setFocus(index);
      graphRef.current?.scrollIntoView({ behavior, block: 'start' });
    },
    [setFocus, behavior],
  );
  const readStep = (index: number) =>
    document.getElementById(`chronicle-step-${index}`)?.scrollIntoView({ behavior, block: 'start' });

  return (
    <PageFrame
      variant={variant}
      name={chronicle?.title ?? null}
      accent={ACCENT}
      wash="var(--accent)"
      resetKey={slug}
      onCollapse={() => collapseChronicle(focus ?? cursor)}
      onClose={closeChronicle}
      closeLabel="Exit tour"
    >
      {isLoading && <PageSkeleton />}
      {isError && <p className="pt-8 text-sm text-destructive">Could not load this chronicle.</p>}

      {chronicle && (
        <>
          <Hero chronicle={chronicle} graph={graph} />
          {graphError && (
            <p className="mt-12 text-[13px] text-destructive">Could not load the chronicle graph.</p>
          )}
          {!graph && !graphError && (
            <div
              className="mt-12 grid animate-pulse place-items-center rounded-xl border bg-muted/40 text-[12px] text-muted-foreground motion-reduce:animate-none"
              style={{ height: variant === 'sheet' ? '56dvh' : 'min(70vh, 640px)' }}
            >
              Gathering the chronicle’s relations…
            </div>
          )}
          {graph && (
            <WholeGraph
              graph={graph}
              rows={rows}
              focus={focus}
              cursor={cursor}
              setFocus={setFocus}
              onRead={readStep}
              sectionRef={graphRef}
            />
          )}

          <Section title="Steps" count={rows.length}>
            <ol>
              {rows.map((row) => (
                <StepItem
                  key={row.entry.entry_id}
                  row={row}
                  total={rows.length}
                  graph={graph}
                  focused={focus === row.index}
                  onFocus={focusInGraph}
                />
              ))}
            </ol>
          </Section>

          <About chronicle={chronicle} />
        </>
      )}
    </PageFrame>
  );
}
