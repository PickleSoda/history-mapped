/**
 * Browse cards. Each card is one stretched link to its standalone page (the
 * title's `::after` covers the card); secondary links (tags, "Open on the
 * globe", the battle's entry) sit above it with `relative z-10`.
 */
import { MapPin, Play, ScrollText } from 'lucide-react';
import { useState } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { MediaCreditLine } from '@/components/atlas/EntityImage';
import { TypeBadge } from '@/components/atlas/GroupBadge';
import { StoryKindIcon, storyKindLabel } from '@/components/atlas/StoryCard';
import { isEmblem, temporalText } from '@/lib/entity-format';
import type { MediaItem } from '@/lib/entity-format';
import { formatYear } from '@/lib/format';
import type { ChronicleSummary } from '@/lib/schemas/chronicle';
import type { CollectionSummary } from '@/lib/schemas/collection';
import type { EntitySummary } from '@/lib/schemas/entity';
import type { MapStoryListItem } from '@/lib/schemas/map-story-list';
import {
  chronicleAtlasHref,
  chroniclePagePath,
  collectionPath,
  entityAtlasHref,
  entityPagePath,
  facetPath,
  storyAtlasHref,
} from '@/lib/site-links';
import { FACETS } from '@/lib/tags';
import type { IndexedTag, TagIndex } from '@/lib/tags';
import { cn } from '@/lib/utils';
import { FacetMark, GlobeLink, TagChipLink } from './browse-kit';
import {
  cardTags,
  chronicleTypeTag,
  entityImage,
  itemsByKindLabel,
  plainText,
  tagCountsLabel,
  yearRangeLabel,
} from './browse-model';
import type { TagNode } from './browse-model';

const CARD =
  'group relative flex flex-col rounded-xl border bg-card p-4 transition hover:border-foreground/25 hover:shadow-sm focus-within:ring-2 focus-within:ring-ring/50';
const STRETCH = "after:absolute after:inset-0 after:content-[''] focus-visible:outline-none";
const SECONDARY = 'relative z-10 underline-offset-2 hover:text-foreground hover:underline';

function CardTitle({ to, className, children }: { to: string; className?: string; children: ReactNode }) {
  return (
    <h3 className={cn('font-heading text-lg leading-snug font-semibold tracking-tight', className)}>
      <Link to={to} className={STRETCH}>
        {children}
      </Link>
    </h3>
  );
}

/** A cover picture for a card (not linked itself, so the card link covers it),
 *  with its credit line; renders nothing if it fails to load. */
function CardCover({ item, className }: { item: MediaItem; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) return null;
  const emblem = isEmblem(item.kind);
  return (
    <div className={cn('overflow-hidden border-b bg-muted/30', className)}>
      <img
        src={item.url}
        alt={item.caption ?? ''}
        loading="lazy"
        decoding="async"
        onError={() => setFailed(true)}
        className={cn('block h-40 w-full', emblem ? 'object-contain p-4' : 'object-cover')}
      />
      <div className="relative z-10 truncate bg-card/70 px-3 py-1">
        <MediaCreditLine item={item} />
      </div>
    </div>
  );
}

// ── Curated sets ──────────────────────────────────────────────────────────

export function CollectionCard({ collection: c }: { collection: CollectionSummary }) {
  const image = entityImage(c.cover);
  const counts = itemsByKindLabel(c.items_by_kind);
  const blurb = c.subtitle ?? plainText(c.description, 140);
  return (
    <article className={cn(CARD, 'overflow-hidden p-0')}>
      {image && <CardCover item={image} />}
      <div className="flex flex-1 flex-col p-4">
        <p className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">Curated set</p>
        <CardTitle to={collectionPath(c.slug)} className="mt-1 text-xl">
          {c.title}
        </CardTitle>
        {blurb && <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{blurb}</p>}
        <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 pt-3 text-xs text-muted-foreground">
          {counts && <span>{counts}</span>}
          {!image && c.cover && <span className="truncate">Featuring {c.cover.name}</span>}
        </div>
      </div>
    </article>
  );
}

// ── Entities ──────────────────────────────────────────────────────────────

export function EntityCard({ entity: e }: { entity: EntitySummary & { image?: unknown; media_refs?: unknown } }) {
  const image = entityImage(e);
  const when = temporalText(e);
  const where = e.location_name && e.location_name !== e.name ? e.location_name : null;
  return (
    <article className={cn(CARD, image && 'overflow-hidden p-0')}>
      {image && <CardCover item={image} />}
      <div className={cn('flex flex-1 flex-col', image && 'p-4')}>
        <div className="flex flex-wrap items-center gap-2">
          <TypeBadge group={e.entity_group} type={e.entity_type} />
          {when && <span className="font-mono text-[11px] text-muted-foreground">{when}</span>}
        </div>
        <CardTitle to={entityPagePath(e.id)} className="mt-2">
          {e.name}
        </CardTitle>
        {e.summary && <p className="mt-1 line-clamp-3 text-sm text-muted-foreground">{e.summary}</p>}
        <div className="mt-auto flex flex-wrap items-center justify-between gap-x-3 gap-y-1 pt-3 text-xs text-muted-foreground">
          {where ? (
            <span className="inline-flex min-w-0 items-center gap-1">
              <MapPin size={12} aria-hidden className="flex-none" />
              <span className="truncate">{where}</span>
            </span>
          ) : (
            <span />
          )}
          <GlobeLink to={entityAtlasHref(e.id)} />
        </div>
      </div>
    </article>
  );
}

// ── Chronicles ────────────────────────────────────────────────────────────

export function ChronicleCard({
  chronicle: c,
  index,
  excludeTag = null,
}: {
  chronicle: ChronicleSummary & { description?: string | null };
  index: TagIndex;
  /** The page's own tag: not repeated on every card. */
  excludeTag?: string | null;
}) {
  const range = yearRangeLabel(c.start_year, c.end_year);
  const type = chronicleTypeTag(c.tags, index);
  const tags = cardTags(c.tags, index, excludeTag);
  const blurb = plainText(c.description, 220);
  return (
    <article className={CARD}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
        <ScrollText size={13} aria-hidden />
        <span className="font-semibold tracking-wider uppercase">Chronicle</span>
        {range && <span className="font-mono">{range}</span>}
        {c.entry_count != null && c.entry_count > 0 && <span>{c.entry_count} steps</span>}
      </div>
      <CardTitle to={chroniclePagePath(c.slug)} className="mt-2 line-clamp-3">
        {c.title}
      </CardTitle>
      {blurb && <p className="mt-1 line-clamp-3 text-sm text-muted-foreground">{blurb}</p>}
      {(type || tags.length > 0) && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {type && type.slug !== excludeTag && <TagChipLink tag={type} className="relative z-10" />}
          {tags.map((t) => (
            <TagChipLink key={t.slug} tag={t} className="relative z-10" />
          ))}
        </div>
      )}
      <div className="mt-auto pt-3">
        <GlobeLink to={chronicleAtlasHref(c.slug)} />
      </div>
    </article>
  );
}

// ── Battle maps ───────────────────────────────────────────────────────────

/** A battle map (map story). It needs the map, so the card opens the globe;
 *  the story's entity and chronicle get their own links. */
export function StoryMapCard({ story: s }: { story: MapStoryListItem }) {
  const meta = [
    s.year != null ? formatYear(s.year) : null,
    s.step_count != null && s.step_count > 0 ? `${s.step_count} steps` : null,
  ].filter(Boolean);
  return (
    <article
      className={cn(
        CARD,
        'border-amber-700/25 bg-gradient-to-br from-amber-50 to-orange-50/50 hover:border-amber-700/50 dark:from-amber-950/40 dark:to-orange-950/20',
      )}
    >
      <div className="flex items-center gap-3">
        <span className="grid size-10 flex-none place-items-center rounded-lg bg-amber-700 text-white shadow-sm">
          <StoryKindIcon kind={s.kind} size={20} />
        </span>
        <div className="min-w-0 text-[11px]">
          <p className="font-semibold tracking-wider text-amber-800 uppercase dark:text-amber-300">
            {storyKindLabel(s.kind)}
          </p>
          {meta.length > 0 && <p className="font-mono text-muted-foreground">{meta.join(' · ')}</p>}
        </div>
      </div>
      <CardTitle to={storyAtlasHref(s.slug)} className="mt-3">
        {s.title}
      </CardTitle>
      <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1 pt-3 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1 font-medium text-amber-800 dark:text-amber-300">
          <Play size={13} aria-hidden /> Play on the globe
        </span>
        {s.entity && (
          <Link to={entityPagePath(s.entity.id)} className={SECONDARY} aria-label={`Read about ${s.entity.name}`}>
            Read the entry
          </Link>
        )}
        {s.chronicle && (
          <Link to={chroniclePagePath(s.chronicle.slug)} className={cn(SECONDARY, 'truncate')}>
            Chronicle: {s.chronicle.title}
          </Link>
        )}
      </div>
    </article>
  );
}

// ── Tags ──────────────────────────────────────────────────────────────────

/** A tag's children as rows: each child links, with its own children after it
 *  ("Middle East · Mesopotamia, Levant, Anatolia"). */
function TagChildren({ nodes }: { nodes: TagNode[] }) {
  if (nodes.length === 0) return null;
  return (
    <ul className="mt-3 grid gap-x-4 gap-y-1.5 border-t pt-3 text-sm sm:grid-cols-2">
      {nodes.map((n) => (
        <li key={n.tag.slug} className="min-w-0">
          <Link to={facetPath(n.tag.facet, n.tag.slug)} className={cn(SECONDARY, 'font-medium')}>
            {n.tag.name}
          </Link>
          {n.children.length > 0 && (
            <span className="text-xs text-muted-foreground">
              {' · '}
              {n.children.map((g, i) => (
                <span key={g.tag.slug}>
                  {i > 0 && ', '}
                  <Link to={facetPath(g.tag.facet, g.tag.slug)} className={SECONDARY}>
                    {g.tag.name}
                  </Link>
                </span>
              ))}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

/**
 * A tag card: name, years (eras), description, counts, and nested children
 * (sub-eras, subregions). `showFacet` labels the facet, for mixed lists.
 */
export function TagCard({
  tag,
  childNodes = [],
  showFacet = false,
  compact = false,
}: {
  tag: IndexedTag;
  childNodes?: TagNode[];
  showFacet?: boolean;
  compact?: boolean;
}) {
  const years = tag.facet === 'era' ? yearRangeLabel(tag.start_year, tag.end_year) : null;
  const counts = tagCountsLabel(tag);
  return (
    <article className={CARD}>
      {showFacet && (
        <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
          <FacetMark facet={tag.facet} />
          {FACETS[tag.facet].label}
        </p>
      )}
      <div className="flex items-baseline justify-between gap-3">
        <CardTitle to={facetPath(tag.facet, tag.slug)} className={cn(compact && 'text-base')}>
          {!showFacet && (
            <span
              aria-hidden
              className="mr-2 inline-block size-2 -translate-y-0.5 rounded-full align-middle"
              style={{ background: FACETS[tag.facet].color }}
            />
          )}
          {tag.name}
        </CardTitle>
        {years && <span className="flex-none font-mono text-[11px] text-muted-foreground">{years}</span>}
      </div>
      {tag.description && (
        <p className={cn('mt-1 text-sm text-muted-foreground', compact ? 'line-clamp-2' : 'line-clamp-3')}>
          {tag.description}
        </p>
      )}
      {counts && <p className="mt-auto pt-2 text-xs text-muted-foreground">{counts}</p>}
      <TagChildren nodes={childNodes} />
    </article>
  );
}
