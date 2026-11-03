import { useMemo, useState } from 'react';
import { Navigate, useParams } from 'react-router-dom';
import { useChronicleList, useEntitiesByTag, useTags } from '@/hooks';
import type { ChronicleListParams } from '@/lib/api';
import { useDocumentMeta } from '@/lib/document-meta';
import { atlasHref, browsePath, facetPath } from '@/lib/site-links';
import type { IndexedTag, TagIndex } from '@/lib/tags';
import {
  BrowseNotFound,
  BrowseSection,
  BrowseShell,
  Breadcrumbs,
  CardSkeletons,
  Eyebrow,
  FacetMark,
  GlobeLink,
  LoadMore,
  Notice,
  QueryNotice,
  Segmented,
  TagChipLink,
} from './browse-kit';
import { childTags, facetLabel, resolveFacetRoute, tagCountsLabel, tagLineage, yearRangeLabel } from './browse-model';
import { ChronicleCard, EntityCard } from './cards';

type ChronicleSort = NonNullable<ChronicleListParams['sort']>;

const SORTS: { value: ChronicleSort; label: string }[] = [
  { value: 'impact', label: 'Most notable' },
  { value: 'chronological', label: 'By date' },
];

function TaggedChronicles({ tag, index }: { tag: IndexedTag; index: TagIndex }) {
  const [sort, setSort] = useState<ChronicleSort>('impact');
  const { data, isLoading, isError, error, refetch, hasNextPage, fetchNextPage, isFetchingNextPage } =
    useChronicleList({ tags: [tag.slug], sort });
  const rows = data?.pages.flatMap((p) => p.data) ?? [];
  const total = data?.pages[0]?.meta.total ?? tag.chronicle_count;

  return (
    <BrowseSection
      id="chronicles"
      title="Chronicles"
      count={total}
      action={rows.length > 1 && <Segmented label="Sort chronicles" value={sort} options={SORTS} onChange={setSort} />}
    >
      {isLoading && <CardSkeletons count={4} className="lg:grid-cols-2" />}
      {isError && <QueryNotice error={error} what="chronicles" onRetry={() => void refetch()} />}
      {data && rows.length === 0 && <Notice title={`No chronicles carry ${tag.name} yet.`} />}
      {rows.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {rows.map((c) => (
            <ChronicleCard key={c.chronicle_id} chronicle={c} index={index} excludeTag={tag.slug} />
          ))}
        </div>
      )}
      {hasNextPage && (
        <LoadMore onClick={() => void fetchNextPage()} loading={isFetchingNextPage} shown={rows.length} total={total} />
      )}
    </BrowseSection>
  );
}

function TaggedEntities({ tag }: { tag: IndexedTag }) {
  const { data, isLoading, isError, error, refetch, hasNextPage, fetchNextPage, isFetchingNextPage } =
    useEntitiesByTag(tag.slug);
  const rows = data?.pages.flatMap((p) => p.data) ?? [];
  const total = data?.pages[0]?.meta.total ?? tag.entity_count;

  return (
    <BrowseSection
      id="entities"
      title="People, places and events"
      count={total}
      lede="The most far-reaching first. Each opens its own page; the globe link shows it on the map."
    >
      {isLoading && <CardSkeletons count={6} />}
      {isError && <QueryNotice error={error} what="entities" onRetry={() => void refetch()} />}
      {data && rows.length === 0 && <Notice title={`Nothing else carries ${tag.name} yet.`} />}
      {rows.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((e) => (
            <EntityCard key={e.id} entity={e} />
          ))}
        </div>
      )}
      {hasNextPage && (
        <LoadMore onClick={() => void fetchNextPage()} loading={isFetchingNextPage} shown={rows.length} total={total} />
      )}
    </BrowseSection>
  );
}

function FacetHeader({ tag, index, tags }: { tag: IndexedTag; index: TagIndex; tags: IndexedTag[] }) {
  const lineage = tagLineage(tag.slug, index);
  const children = useMemo(() => childTags(tag.slug, tags), [tag.slug, tags]);
  const years = yearRangeLabel(tag.start_year, tag.end_year);
  const counts = tagCountsLabel(tag);
  const label = facetLabel(tag.facet);

  return (
    <header className="max-w-3xl">
      <Breadcrumbs
        items={[
          { label: 'Browse', to: browsePath() },
          { label, to: `${browsePath()}#${tag.facet}` },
          ...lineage.map((t) => ({ label: t.name, to: facetPath(t.facet, t.slug) })),
          { label: tag.name },
        ]}
      />
      <Eyebrow>
        <FacetMark facet={tag.facet} />
        {label}
      </Eyebrow>
      <h1 className="mt-1 font-heading text-4xl font-semibold tracking-tight sm:text-5xl">{tag.name}</h1>
      {years && <p className="mt-2 font-mono text-sm text-muted-foreground">{years}</p>}
      {tag.description && <p className="mt-3 text-lg text-muted-foreground">{tag.description}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
        {counts && <span>{counts}</span>}
        {tag.chronicle_count > 0 && (
          <GlobeLink to={atlasHref({ ct: tag.slug })} label="These chronicles on the globe" className="text-sm" />
        )}
      </div>
      {children.length > 0 && (
        <div className="mt-5">
          <p className="mb-2 text-xs text-muted-foreground">Narrower</p>
          <div className="flex flex-wrap gap-1.5">
            {children.map((c) => (
              <TagChipLink key={c.slug} tag={c} count={c.chronicle_count + c.entity_count} />
            ))}
          </div>
        </div>
      )}
    </header>
  );
}

/** `/browse/:facet/:tag` (spec D4): a tag's header, its narrower tags, and
 *  the chronicles and entities that carry it, each paged. */
export function BrowseFacetPage() {
  const { facet = '', tag: slug = '' } = useParams();
  const { tags, index, isLoading, isError, error, refetch } = useTags();
  const route = useMemo(() => resolveFacetRoute(facet, slug, index), [facet, slug, index]);
  const tag = route.status === 'ok' ? route.tag : null;
  useDocumentMeta({ title: tag?.name ?? (isLoading ? 'Browse' : 'Not found'), description: tag?.description });

  if (isLoading) {
    return (
      <BrowseShell>
        <div className="max-w-3xl animate-pulse space-y-3" aria-hidden>
          <div className="h-3 w-40 rounded bg-muted" />
          <div className="h-10 w-2/3 rounded bg-muted" />
          <div className="h-4 w-full rounded bg-muted" />
        </div>
        <CardSkeletons count={4} className="mt-10" />
      </BrowseShell>
    );
  }
  if (isError) {
    return (
      <BrowseShell className="max-w-3xl">
        <Breadcrumbs items={[{ label: 'Browse', to: browsePath() }, { label: slug }]} />
        <QueryNotice error={error} what="this tag" onRetry={() => void refetch()} />
      </BrowseShell>
    );
  }
  if (route.status === 'redirect') return <Navigate to={facetPath(route.facet, slug)} replace />;
  if (!tag) {
    return (
      <BrowseNotFound title="Nothing is filed under that tag">
        <p>
          There is no {facet ? `“${facet}”` : ''} tag called “{slug}”. Browse the eras, regions and themes instead.
        </p>
      </BrowseNotFound>
    );
  }

  return (
    <BrowseShell>
      <FacetHeader tag={tag} index={index} tags={tags} />
      <div className="mt-8">
        {/* The vocabulary's counts decide which lists to fetch (kinds of
            chronicle tag no entities, for one). */}
        {tag.chronicle_count > 0 && <TaggedChronicles key={`c-${tag.slug}`} tag={tag} index={index} />}
        {tag.entity_count > 0 && <TaggedEntities key={`e-${tag.slug}`} tag={tag} />}
        {tag.chronicle_count === 0 && tag.entity_count === 0 && (
          <Notice title={`Nothing carries ${tag.name} yet.`}>Its narrower tags may have more.</Notice>
        )}
      </div>
    </BrowseShell>
  );
}
