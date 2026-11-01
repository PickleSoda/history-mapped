import { useMemo, useState } from 'react';
import { useMapStoryList } from '@/hooks';
import type { MapStoryListParams } from '@/lib/api';
import {
  BrowseShell,
  Breadcrumbs,
  CardSkeletons,
  FilterChips,
  GlobeLink,
  LoadMore,
  Notice,
  QueryNotice,
  Segmented,
} from './browse-kit';
import { storyKindName, storyKinds } from './browse-model';
import { StoryMapCard } from './cards';
import { atlasHref, browsePath } from './links';
import { useBrowseDocumentTitle } from './useBrowseDocumentTitle';

type StorySort = NonNullable<MapStoryListParams['sort']>;

const SORTS: { value: StorySort; label: string }[] = [
  { value: 'year', label: 'By year' },
  { value: 'title', label: 'By title' },
];

/** `/browse/stories` (spec D4): every battle map (map story) as a card, with
 *  kind filters and a year / title sort. Cards open the story on the globe. */
export function StoriesPage() {
  useBrowseDocumentTitle(
    'Battle maps',
    'Step-by-step maps of battles, sieges, epidemics and trade routes, played on the History Mapped globe.',
  );
  const [kind, setKind] = useState<string | null>(null);
  const [sort, setSort] = useState<StorySort>('year');
  // The unfiltered list names the kinds for the chips; with no kind picked it
  // is the same query (one request).
  const all = useMapStoryList({ sort });
  const list = useMapStoryList(kind ? { kind, sort } : { sort });
  const allRows = useMemo(() => all.data?.pages.flatMap((p) => p.data) ?? [], [all.data]);
  const kinds = useMemo(() => storyKinds(allRows), [allRows]);
  const countsKnown = all.data != null && !all.hasNextPage;

  const { data, isLoading, isError, error, refetch, hasNextPage, fetchNextPage, isFetchingNextPage } = list;
  const rows = data?.pages.flatMap((p) => p.data) ?? [];
  const total = data?.pages[0]?.meta.total;

  return (
    <BrowseShell>
      <Breadcrumbs items={[{ label: 'Browse', to: browsePath() }, { label: 'Battle maps' }]} />
      <header className="max-w-3xl">
        <h1 className="font-heading text-4xl font-semibold tracking-tight sm:text-5xl">Battle maps</h1>
        <p className="mt-3 text-lg text-muted-foreground">
          Step-by-step maps of battles and sieges, and of epidemics and trade routes, drawn on the historical
          borders of their day. Each one plays on the globe.
        </p>
        <GlobeLink to={atlasHref()} label="Open the globe" className="mt-3 text-sm" />
      </header>

      <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t pt-6">
        {kinds.length > 1 ? (
          <FilterChips
            label="Kind of map"
            value={kind}
            onChange={setKind}
            options={[
              { value: null, label: 'All', count: countsKnown ? allRows.length : undefined },
              ...kinds.map((k) => ({
                value: k.kind,
                label: storyKindName(k.kind),
                count: countsKnown ? k.count : undefined,
              })),
            ]}
          />
        ) : (
          <span />
        )}
        <Segmented label="Sort battle maps" value={sort} options={SORTS} onChange={setSort} />
      </div>

      <div className="mt-5">
        {isLoading && <CardSkeletons count={6} />}
        {isError && (
          <QueryNotice
            error={error}
            what="battle maps"
            missing="The battle-map index is on its way. The maps already play on the globe."
            onRetry={() => void refetch()}
          />
        )}
        {data && rows.length === 0 && (
          <Notice title={kind ? `No ${storyKindName(kind).toLowerCase()} yet.` : 'No battle maps yet.'} />
        )}
        {rows.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {rows.map((s) => (
              <StoryMapCard key={s.id} story={s} />
            ))}
          </div>
        )}
        {hasNextPage && (
          <LoadMore
            onClick={() => void fetchNextPage()}
            loading={isFetchingNextPage}
            shown={rows.length}
            total={total}
          />
        )}
      </div>
    </BrowseShell>
  );
}
