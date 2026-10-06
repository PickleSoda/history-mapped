import { Clock, ExternalLink, Hash, ImageIcon, MapPin, ScrollText } from 'lucide-react';
import { useMemo, useState } from 'react';
import { TypeBadge } from '@/components/atlas/GroupBadge';
import {
  ImpactMeter,
  PageFrame,
  PageSkeleton,
  PageTitle,
  Section,
  Stat,
  StatGrid,
} from '@/components/atlas/page-kit';
import type { PageVariant } from '@/components/atlas/page-kit';
import {
  chronicleByRelationship,
  RelationshipTimeline,
} from '@/components/atlas/RelationshipTimeline';
import { RelationGraph } from '@/components/graph';
import {
  useChronicleNav,
  useEntity,
  useEntityChronicles,
  useEntityConnections,
  useEntityGraph,
  useEntityTimeline,
  useFullPage,
  useMapFocus,
  useSelection,
  useTimeState,
} from '@/hooks';
import {
  attributeRows,
  citationRows,
  dateText,
  humanise,
  mediaItems,
  numericYear,
  spanText,
} from '@/lib/entity-format';
import { formatYear } from '@/lib/format';
import { GROUPS } from '@/lib/groups';
import { VERIFICATION_STATUSES } from '@/lib/schemas/entity';
import type {
  ConfidenceLevel,
  EntityDetail,
  EntityTimelineEntry,
  VerificationStatus,
} from '@/lib/schemas/entity';
import { cn } from '@/lib/utils';

export type { PageVariant } from '@/components/atlas/page-kit';

// ── Small building blocks ──────────────────────────────────────────────────

const CONFIDENCE_BARS: Record<ConfidenceLevel, number> = { high: 3, medium: 2, low: 1, unresolved: 0 };

/** Confidence as a three-bar signal, explained by its label. */
function ConfidenceSignal({ level, notes }: { level: ConfidenceLevel | null; notes: string | null }) {
  const bars = level ? CONFIDENCE_BARS[level] : 0;
  return (
    <span className="flex items-center gap-2" title={notes ?? undefined}>
      <span aria-hidden className="flex items-end gap-0.5">
        {[1, 2, 3].map((b) => (
          <span
            key={b}
            className={cn('w-1 rounded-sm', b <= bars ? 'bg-foreground/80' : 'bg-border')}
            style={{ height: 4 + b * 3 }}
          />
        ))}
      </span>
      <span className="capitalize">{level ?? 'Not rated'}</span>
    </span>
  );
}

/** Verification as a four-rung ladder, draft → expert. */
function VerificationLadder({ status }: { status: VerificationStatus | null }) {
  const rung = status ? VERIFICATION_STATUSES.indexOf(status) : -1;
  return (
    <span className="flex items-center gap-2">
      <span aria-hidden className="flex gap-0.5">
        {VERIFICATION_STATUSES.map((s, i) => (
          <span key={s} className={cn('size-1.5 rounded-full', i <= rung ? 'bg-foreground/80' : 'bg-border')} />
        ))}
      </span>
      <span>{status ? humanise(status) : 'Unknown'}</span>
    </span>
  );
}

// ── Content sections ───────────────────────────────────────────────────────

function DatesLine({ entity }: { entity: EntityDetail }) {
  const start = dateText(entity.temporal_start);
  const end = dateText(entity.temporal_end);
  const text =
    entity.temporal_display_range ??
    (start && end ? `${start} – ${end}` : (start ?? end ?? entity.era_label));
  if (!text) return null;
  const raw = [entity.date_raw && `Source: “${entity.date_raw}”`, entity.date_confidence && `Date confidence: ${entity.date_confidence}`]
    .filter(Boolean)
    .join(' · ');
  return (
    <span className="inline-flex items-center gap-1.5">
      <Clock size={14} className="flex-none" />
      <span
        title={raw || undefined}
        className={cn('font-mono text-[12.5px]', raw && 'cursor-help underline decoration-dotted underline-offset-4')}
      >
        {text}
      </span>
      {raw && <span className="sr-only">({raw})</span>}
    </span>
  );
}

function Hero({ entity }: { entity: EntityDetail }) {
  const g = GROUPS[entity.entity_group];
  const { setInstant } = useTimeState();
  const { collapse } = useFullPage();
  const { focusGeometries } = useMapFocus();
  const alt = entity.alternative_names.filter((n) => n !== entity.name);
  const startYear = numericYear(entity.temporal_start) ?? numericYear(entity.temporal_end);
  const span = spanText(entity.temporal_start, entity.temporal_end);

  return (
    <header className="pt-8">
      <TypeBadge group={entity.entity_group} type={entity.entity_type} />
      <PageTitle>{entity.name}</PageTitle>
      {alt.length > 0 && (
        <p className="mt-2.5 font-heading text-[15px] italic text-muted-foreground">
          <span className="not-italic text-[11px] font-sans font-semibold uppercase tracking-wider">
            Also known as
          </span>{' '}
          {alt.slice(0, 8).join(' · ')}
          {alt.length > 8 && ` · +${alt.length - 8}`}
        </p>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-[13px] text-foreground/80">
        <DatesLine entity={entity} />
        {startYear != null && (
          <button
            type="button"
            onClick={() => {
              setInstant(startYear);
              collapse();
            }}
            className="text-[12px] text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            View the map in {formatYear(startYear)}
          </button>
        )}
        {entity.geom != null ? (
          <button
            type="button"
            onClick={() => {
              collapse();
              focusGeometries([entity.geom]);
            }}
            className="inline-flex items-center gap-1.5 underline-offset-4 hover:underline"
            title="Show on the map"
          >
            <MapPin size={14} style={{ color: g.color }} />
            {entity.location_name ?? 'Show on map'}
          </button>
        ) : (
          entity.location_name && (
            <span className="inline-flex items-center gap-1.5">
              <MapPin size={14} className="text-muted-foreground" />
              {entity.location_name}
              <span className="text-[11px] text-muted-foreground">(not placed on the map)</span>
            </span>
          )
        )}
        {entity.wikidata_id && (
          <a
            href={`https://www.wikidata.org/wiki/${entity.wikidata_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-mono text-[12px] text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            Wikidata {entity.wikidata_id} <ExternalLink size={12} />
          </a>
        )}
      </div>

      {/* Stats block — the Civilopedia ledger. */}
      <StatGrid>
        <Stat label="Began">{dateText(entity.temporal_start) ?? '—'}</Stat>
        <Stat label="Ended">{dateText(entity.temporal_end) ?? '—'}</Stat>
        <Stat label="Span">{span ?? '—'}</Stat>
        <Stat label="Impact">
          {entity.impact_score != null ? <ImpactMeter value={entity.impact_score} color={g.color} /> : '—'}
        </Stat>
        <Stat label="Confidence">
          <ConfidenceSignal level={entity.confidence} notes={entity.confidence_notes} />
        </Stat>
        <Stat label="Verification">
          <VerificationLadder status={entity.verification_status} />
        </Stat>
      </StatGrid>
    </header>
  );
}

function Prose({ entity }: { entity: EntityDetail }) {
  const g = GROUPS[entity.entity_group];
  if (!entity.summary && !entity.significance) return null;
  return (
    <div className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      {entity.summary && (
        <Section title="Summary" className="mt-0">
          <p className="font-heading text-[19px] leading-[1.6] text-foreground/90 [font-variation-settings:'SOFT'_50]">
            {entity.summary}
          </p>
        </Section>
      )}
      {entity.significance && (
        <Section title="Significance" className="mt-0">
          <blockquote
            className="border-l-[3px] pl-4 text-[15px] leading-relaxed text-foreground/85"
            style={{ borderColor: g.color }}
          >
            {entity.significance}
          </blockquote>
        </Section>
      )}
    </div>
  );
}

function GraphSection({ entity, variant }: { entity: EntityDetail; variant: PageVariant }) {
  const [hops, setHops] = useState<1 | 2>(1);
  const { data, isLoading, isError, isFetching } = useEntityGraph(entity.id, { depth: hops });
  const label = `Relation graph of ${entity.name}`;
  return (
    <Section
      title="Connections"
      count={data ? data.edges.length : undefined}
      aside={
        <div className="flex items-center gap-0.5 rounded-lg bg-muted p-0.5" role="group" aria-label="Graph depth">
          {([1, 2] as const).map((h) => (
            <button
              key={h}
              type="button"
              aria-pressed={hops === h}
              onClick={() => setHops(h)}
              className={cn(
                'h-6 rounded-md px-2 text-[11px] font-medium transition-colors',
                hops === h ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {h} hop{h === 2 ? 's' : ''}
            </button>
          ))}
        </div>
      }
    >
      <p className="-mt-2 mb-3 text-[12px] text-muted-foreground">
        Click an entity to see how it relates to {entity.name}; expand it to follow its own relations.
        {isFetching && !isLoading && ' Loading…'}
      </p>
      {isError && <p className="text-[13px] text-destructive">Could not load the relation graph.</p>}
      {isLoading && (
        <div
          className="grid animate-pulse place-items-center rounded-xl border bg-muted/40 text-[12px] text-muted-foreground motion-reduce:animate-none"
          style={{ height: variant === 'sheet' ? '52dvh' : 'min(64vh, 560px)' }}
        >
          Gathering relations…
        </div>
      )}
      {data && data.nodes.length <= 1 && (
        <p className="text-[13px] text-muted-foreground">No relations recorded yet.</p>
      )}
      {data && data.nodes.length > 1 && (
        <RelationGraph
          nodes={data.nodes}
          edges={data.edges}
          rootId={data.root}
          truncated={data.truncated}
          height={variant === 'sheet' ? '52dvh' : undefined}
          label={label}
        />
      )}
    </Section>
  );
}

function AttributesAndTags({ entity }: { entity: EntityDetail }) {
  const rows = attributeRows(entity.attributes);
  if (rows.length === 0 && entity.tags.length === 0) return null;
  return (
    <Section title={rows.length > 0 ? 'Attributes' : 'Tags'} count={rows.length || undefined}>
      {rows.length > 0 && (
        <dl className="grid gap-x-8 sm:grid-cols-2">
          {rows.map((r) => (
            <div key={r.key} className="flex gap-4 border-b border-dashed py-2 text-[13px]">
              <dt className="w-2/5 flex-none text-muted-foreground">{r.label}</dt>
              <dd className="min-w-0 flex-1 break-words">{r.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {entity.tags.length > 0 && (
        <ul className={cn('flex flex-wrap gap-1.5', rows.length > 0 && 'mt-4')} aria-label="Tags">
          {entity.tags.map((t) => (
            <li
              key={t}
              className="inline-flex items-center gap-0.5 rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground"
            >
              <Hash size={11} />
              {t}
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function Chronicles({ id }: { id: string }) {
  const { data } = useEntityChronicles(id);
  const { enter } = useChronicleNav();
  if (!data || data.data.length === 0) return null;
  return (
    <Section title="In chronicles" count={data.data.length}>
      <div className="flex flex-wrap gap-2">
        {data.data.map((c) => (
          <button
            key={c.chronicle_id}
            type="button"
            onClick={() => enter(c.slug)}
            className="inline-flex items-center gap-1.5 rounded-full border bg-card px-3 py-1.5 text-[12px] shadow-xs transition-colors hover:bg-muted"
            title="Open this chronicle"
          >
            <ScrollText size={13} className="text-muted-foreground" />
            <span className="font-heading">{c.title}</span>
          </button>
        ))}
      </div>
    </Section>
  );
}

function entryYears(e: EntityTimelineEntry): string | null {
  if (e.start_year == null && e.end_year == null) return null;
  if (e.start_year != null && e.end_year != null && e.end_year !== e.start_year) {
    return `${formatYear(e.start_year)} – ${formatYear(e.end_year)}`;
  }
  return formatYear((e.start_year ?? e.end_year) as number);
}

const TIMELINE_PAGE = 40;

function TimelineEntries({ id }: { id: string }) {
  const { data, isLoading } = useEntityTimeline(id);
  const { select } = useSelection();
  const [all, setAll] = useState(false);
  const entries = data?.data ?? [];
  const shown = all ? entries : entries.slice(0, TIMELINE_PAGE);
  return (
    <Section title="Timeline" count={data ? entries.length : undefined}>
      {isLoading && <p className="text-[13px] text-muted-foreground">Loading…</p>}
      {data && entries.length === 0 && (
        <p className="text-[13px] text-muted-foreground">No timeline entries.</p>
      )}
      {shown.length > 0 && (
        <ol className="relative space-y-4 pl-5">
          <span aria-hidden className="absolute bottom-2 left-2 top-2 w-px bg-border" />
          {shown.map((e) => (
            <li key={e.id} className="relative">
              <span
                aria-hidden
                className="absolute -left-[15px] top-1.5 size-2.5 rounded-full border-2 border-background bg-muted-foreground/60"
              />
              <div className="flex flex-wrap items-center gap-2">
                {entryYears(e) && (
                  <span className="font-mono text-[10px] text-muted-foreground">{entryYears(e)}</span>
                )}
                {e.relationship_type && (
                  <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                    {e.relationship_type.replace(/_/g, ' ')}
                  </span>
                )}
                {e.entry_kind && e.entry_kind !== 'relationship' && (
                  <span className="rounded-full bg-muted px-1.5 py-px text-[10px] capitalize text-muted-foreground">
                    {humanise(e.entry_kind)}
                  </span>
                )}
              </div>
              {e.related_entity_id ? (
                <button
                  type="button"
                  onClick={() => select(e.related_entity_id as string)}
                  className="mt-0.5 text-left text-[13px] font-medium underline-offset-4 hover:underline"
                >
                  {e.title ?? e.related_entity_name}
                </button>
              ) : (
                e.title && <p className="mt-0.5 text-[13px] font-medium">{e.title}</p>
              )}
              {e.description && (
                <p className="mt-0.5 text-[12px] leading-snug text-foreground/70">{e.description}</p>
              )}
            </li>
          ))}
        </ol>
      )}
      {entries.length > TIMELINE_PAGE && (
        <button
          type="button"
          onClick={() => setAll((v) => !v)}
          className="mt-4 text-[12px] text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          {all ? 'Show fewer' : `Show all ${entries.length}`}
        </button>
      )}
    </Section>
  );
}

function SourcesAndMedia({ entity }: { entity: EntityDetail }) {
  const rows = citationRows(entity.source_citations);
  const media = mediaItems(entity.media_refs);
  return (
    <Section title="Sources & media" count={rows.length + media.length || undefined}>
      {rows.length === 0 && media.length === 0 && (
        <p className="text-[13px] text-muted-foreground">No sources recorded.</p>
      )}
      {rows.length > 0 && (
        <dl className="divide-y divide-dashed rounded-xl border bg-card px-4 text-[13px]">
          {rows.map((r, i) => (
            <div key={`${r.label}-${i}`} className="flex flex-col gap-0.5 py-2.5 sm:flex-row sm:gap-4">
              <dt className="flex-none text-muted-foreground sm:w-44">{r.label}</dt>
              <dd className="min-w-0 flex-1 break-words font-mono text-[12px]">
                {r.href ? (
                  <a
                    href={r.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 underline decoration-border underline-offset-4 hover:decoration-foreground"
                  >
                    {r.value} <ExternalLink size={11} className="flex-none" />
                  </a>
                ) : (
                  r.value
                )}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {media.length > 0 && (
        <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {media.map((m) => (
            <li key={m.url}>
              <a
                href={m.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group block overflow-hidden rounded-lg border bg-card"
              >
                {m.isImage ? (
                  <img
                    src={m.url}
                    alt={m.caption ?? ''}
                    loading="lazy"
                    className="aspect-[4/3] w-full object-cover transition-opacity group-hover:opacity-90"
                  />
                ) : (
                  <span className="grid aspect-[4/3] place-items-center text-muted-foreground">
                    <ImageIcon size={22} />
                  </span>
                )}
                <span className="block truncate px-2 py-1.5 text-[11px] text-muted-foreground">
                  {m.caption ?? new URL(m.url).hostname}
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

// ── The page ───────────────────────────────────────────────────────────────

/**
 * The full entity page: everything the API knows about one entity, as a
 * scrollable document with a sticky header. Rendered by the desktop page host
 * (slides up over the map) and by the mobile sheet at its full snap. Takes the
 * id as a prop (not from the URL) so the host can keep it on screen while the
 * page slides away after Close.
 */
export function EntityPage({ id, variant = 'page' }: { id: string; variant?: PageVariant }) {
  const { data: entity, isLoading, isError } = useEntity(id);
  const { data: connections } = useEntityConnections(id);
  const { data: chronicles } = useEntityChronicles(id);
  const { collapse, closeEntity } = useFullPage();
  const relChronicle = useMemo(() => chronicleByRelationship(chronicles?.data), [chronicles]);
  const g = entity ? GROUPS[entity.entity_group] : null;

  return (
    <PageFrame
      variant={variant}
      name={entity?.name ?? null}
      accent={g?.color}
      wash={g?.soft}
      resetKey={id}
      onCollapse={collapse}
      onClose={closeEntity}
    >
      {isLoading && <PageSkeleton />}
      {isError && <p className="pt-8 text-sm text-destructive">Could not load this entity.</p>}

      {entity && (
        <>
          <Hero entity={entity} />
          <Prose entity={entity} />
          <GraphSection entity={entity} variant={variant} />
          <AttributesAndTags entity={entity} />
          <Chronicles id={entity.id} />
          <div className="grid gap-x-12 xl:grid-cols-2">
            <Section title="Relationships" count={connections?.data.length}>
              {connections && connections.data.length > 0 ? (
                <RelationshipTimeline
                  rels={connections.data}
                  selfId={entity.id}
                  relChronicle={relChronicle}
                />
              ) : (
                <p className="text-[13px] text-muted-foreground">
                  {connections ? 'No relationships recorded.' : 'Loading…'}
                </p>
              )}
            </Section>
            <TimelineEntries id={entity.id} />
          </div>
          <SourcesAndMedia entity={entity} />
        </>
      )}
    </PageFrame>
  );
}
