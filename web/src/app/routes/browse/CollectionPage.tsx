import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { EntityImage } from '@/components/atlas/EntityImage';
import { TypeBadge } from '@/components/atlas/GroupBadge';
import { useCollection, useTags } from '@/hooks';
import { errorStatus } from '@/lib/api/errors';
import { useDocumentMeta } from '@/lib/document-meta';
import type { Collection, CollectionItem, CollectionItemKind } from '@/lib/schemas/collection';
import { browsePath, entityPagePath } from '@/lib/site-links';
import type { TagIndex } from '@/lib/tags';
import {
  BrowseNotFound,
  BrowseShell,
  Breadcrumbs,
  CardSkeletons,
  Eyebrow,
  FilterChips,
  Markdown,
  Notice,
  QueryNotice,
} from './browse-kit';
import {
  countItemsByKind,
  entityImage,
  filterItems,
  itemKindFilters,
  itemKindHeading,
  itemsByKindLabel,
  numberItems,
} from './browse-model';
import { ChronicleCard, EntityCard, StoryMapCard, TagCard } from './cards';

function ItemCard({ item, index }: { item: CollectionItem; index: TagIndex }) {
  switch (item.kind) {
    case 'entity':
      return <EntityCard entity={item.entity} />;
    case 'chronicle':
      return <ChronicleCard chronicle={item.chronicle} index={index} />;
    case 'story':
      return <StoryMapCard story={item.story} />;
    case 'tag':
      return <TagCard tag={index.get(item.tag.slug) ?? { ...item.tag, order: 0 }} showFacet />;
  }
}

function CollectionHeader({ set }: { set: Collection }) {
  const image = entityImage(set.cover);
  const counts = itemsByKindLabel(set.items_by_kind);
  return (
    <header className={image ? 'grid gap-6 md:grid-cols-[minmax(0,1fr)_18rem] md:gap-10' : 'max-w-3xl'}>
      <div className="min-w-0">
        <Eyebrow>Curated set</Eyebrow>
        <h1 className="mt-1 font-heading text-4xl font-semibold tracking-tight sm:text-5xl">{set.title}</h1>
        {set.subtitle && <p className="mt-2 text-xl text-muted-foreground">{set.subtitle}</p>}
        <Markdown text={set.description} className="mt-4 max-w-2xl text-base leading-relaxed" />
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
          {counts && <span>{counts}</span>}
          {!image && set.cover && (
            <span className="inline-flex items-center gap-2">
              Featuring
              <Link to={entityPagePath(set.cover.id)} className="text-foreground underline-offset-2 hover:underline">
                {set.cover.name}
              </Link>
              <TypeBadge group={set.cover.entity_group} type={set.cover.entity_type} />
            </span>
          )}
        </div>
      </div>
      {image && set.cover && (
        <div className="min-w-0">
          <EntityImage item={image} imgClassName="max-h-72" showCaption={false} />
          <p className="mt-2 text-xs text-muted-foreground">
            Cover:{' '}
            <Link to={entityPagePath(set.cover.id)} className="text-foreground underline-offset-2 hover:underline">
              {set.cover.name}
            </Link>
          </p>
        </div>
      )}
    </header>
  );
}

function CollectionItems({ set, index }: { set: Collection; index: TagIndex }) {
  const [kind, setKind] = useState<CollectionItemKind | null>(null);
  const numbered = useMemo(() => numberItems(set.items), [set.items]);
  const counts = useMemo(() => countItemsByKind(numbered), [numbered]);
  const kinds = itemKindFilters(counts);
  const shown = filterItems(numbered, kind);

  if (numbered.length === 0) {
    return <Notice title="This set is empty for now.">Its items are still being chosen.</Notice>;
  }
  return (
    <>
      {kinds.length > 0 && (
        <div className="mb-5">
          <FilterChips
            label="Show"
            value={kind}
            onChange={setKind}
            options={[
              { value: null, label: 'All', count: numbered.length },
              ...kinds.map((k) => ({ value: k, label: itemKindHeading(k), count: counts[k] })),
            ]}
          />
        </div>
      )}
      <ol className="space-y-5" aria-label="Items, in the editor’s order">
        {shown.map(({ position, key, item }) => (
          <li key={key} className="flex gap-3 sm:gap-4">
            <span
              aria-label={`Item ${position}`}
              className="mt-3 grid size-7 flex-none place-items-center rounded-full border bg-card font-mono text-xs text-muted-foreground"
            >
              {position}
            </span>
            <div className="min-w-0 flex-1">
              <ItemCard item={item} index={index} />
              {item.note && (
                <p className="mt-2 border-l-2 pl-3 text-sm text-muted-foreground italic">{item.note}</p>
              )}
            </div>
          </li>
        ))}
      </ol>
    </>
  );
}

/** `/browse/collections/:slug` (spec D4): a curated set, its cover and
 *  description, then its items in the author's order (filterable by kind,
 *  numbers kept). */
export function CollectionPage() {
  const { slug = '' } = useParams();
  const { data: set, isLoading, isError, error, refetch } = useCollection(slug || null);
  const { index } = useTags();
  const missing = isError && errorStatus(error) === 404;
  useDocumentMeta({ title: set?.title ?? (missing ? 'Not found' : 'Curated set'), description: set?.subtitle ?? set?.description });

  if (missing) {
    return (
      <BrowseNotFound title="No such curated set">
        <p>There is no set called “{slug}”. It may have been renamed; the browse page lists every set.</p>
      </BrowseNotFound>
    );
  }

  return (
    <BrowseShell>
      <Breadcrumbs
        items={[
          { label: 'Browse', to: browsePath() },
          { label: 'Curated sets', to: `${browsePath()}#sets` },
          { label: set?.title ?? slug },
        ]}
      />
      {isLoading && (
        <>
          <div className="max-w-3xl animate-pulse space-y-3" aria-hidden>
            <div className="h-3 w-24 rounded bg-muted" />
            <div className="h-10 w-2/3 rounded bg-muted" />
            <div className="h-4 w-full rounded bg-muted" />
            <div className="h-4 w-5/6 rounded bg-muted" />
          </div>
          <CardSkeletons count={3} className="mt-10 max-w-3xl sm:grid-cols-1 lg:grid-cols-1" />
        </>
      )}
      {isError && <QueryNotice error={error} what="this set" onRetry={() => void refetch()} />}
      {set && (
        <>
          <CollectionHeader set={set} />
          <div className="mt-10 max-w-3xl border-t pt-8">
            <CollectionItems set={set} index={index} />
          </div>
        </>
      )}
    </BrowseShell>
  );
}
