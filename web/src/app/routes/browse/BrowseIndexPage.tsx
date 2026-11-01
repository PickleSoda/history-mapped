import { ArrowRight } from 'lucide-react';
import { useEffect, useMemo } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useChronicleList, useCollections, useMapStoryList, useTags } from '@/hooks';
import { BrowseSection, BrowseShell, CardSkeletons, Notice, QueryNotice } from './browse-kit';
import { facetSections } from './browse-model';
import type { FacetSection } from './browse-model';
import { ChronicleCard, CollectionCard, StoryMapCard, TagCard } from './cards';
import { storiesPath } from './links';
import { useBrowseDocumentTitle } from './useBrowseDocumentTitle';

const STRIP = 6;

const FACET_LEDES: Record<string, string> = {
  era: 'From the first farmers to the present, in the periods the atlas uses.',
  region: 'Continents and the regions within them, plus seas and routes that cross them.',
  theme: 'War, faith, trade, ideas: the threads that run through every era.',
  type: 'Chronicles are told in a few ways: a region over time, an empire, a war, a people, a theme.',
};

const MORE_LINK =
  'inline-flex items-center gap-1 text-sm text-muted-foreground underline-offset-2 hover:text-foreground hover:underline';

function CuratedSets() {
  const { data, isLoading, isError, error, refetch } = useCollections();
  const sets = data?.data ?? [];
  return (
    <BrowseSection
      id="sets"
      title="Curated sets"
      lede="Hand-picked paths through the atlas: chronicles, battle maps and the people, places and events behind them."
    >
      {isLoading && <CardSkeletons count={3} itemClassName="h-56" />}
      {isError && (
        <QueryNotice
          error={error}
          what="curated sets"
          missing="The first curated sets are on their way."
          onRetry={() => void refetch()}
        />
      )}
      {data && sets.length === 0 && <Notice title="No curated sets yet.">The first sets are being written.</Notice>}
      {sets.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {sets.map((c) => (
            <CollectionCard key={c.slug} collection={c} />
          ))}
        </div>
      )}
    </BrowseSection>
  );
}

function FacetGrid({ section }: { section: FacetSection }) {
  const { facet, heading, roots } = section;
  // Regions and eras carry their children inside the card, so they get
  // wider cards; themes and kinds are flat and compact.
  const nested = roots.some((n) => n.children.length > 0);
  return (
    <BrowseSection id={facet} title={heading} lede={FACET_LEDES[facet]}>
      <div className={nested ? 'grid gap-3 md:grid-cols-2' : 'grid gap-3 sm:grid-cols-2 lg:grid-cols-3'}>
        {roots.map((n) => (
          <TagCard key={n.tag.slug} tag={n.tag} childNodes={n.children} compact={!nested} />
        ))}
      </div>
    </BrowseSection>
  );
}

function ChronicleStrip() {
  const { index } = useTags();
  const { data, isLoading, isError, error, refetch } = useChronicleList({ sort: 'impact' });
  const rows = (data?.pages[0]?.data ?? []).slice(0, STRIP);
  const total = data?.pages[0]?.meta.total;
  return (
    <BrowseSection
      id="chronicles"
      title="Chronicles"
      count={total}
      lede="Narrated tours, step by step, each with its own page and its own path across the globe. The most far-reaching first; the tag on each card opens everything of that kind."
    >
      {isLoading && <CardSkeletons count={STRIP} />}
      {isError && <QueryNotice error={error} what="chronicles" onRetry={() => void refetch()} />}
      {data && rows.length === 0 && <Notice title="No chronicles yet." />}
      {rows.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((c) => (
            <ChronicleCard key={c.chronicle_id} chronicle={c} index={index} />
          ))}
        </div>
      )}
    </BrowseSection>
  );
}

function StoryStrip() {
  const { data, isLoading, isError, error, refetch } = useMapStoryList({ sort: 'year', perPage: 12 });
  const rows = (data?.pages[0]?.data ?? []).slice(0, STRIP);
  const total = data?.pages[0]?.meta.total;
  return (
    <BrowseSection
      id="battle-maps"
      title="Battle maps"
      count={total}
      lede="Step-by-step maps of battles, sieges, epidemics and trade routes. They play on the globe."
      action={
        <Link to={storiesPath()} className={MORE_LINK}>
          All battle maps <ArrowRight size={14} aria-hidden />
        </Link>
      }
    >
      {isLoading && <CardSkeletons count={3} />}
      {isError && (
        <QueryNotice
          error={error}
          what="battle maps"
          missing="The battle-map index is on its way. The maps already play on the globe."
          onRetry={() => void refetch()}
        />
      )}
      {data && rows.length === 0 && <Notice title="No battle maps yet." />}
      {rows.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((s) => (
            <StoryMapCard key={s.id} story={s} />
          ))}
        </div>
      )}
    </BrowseSection>
  );
}

const JUMPS: { id: string; label: string }[] = [
  { id: 'sets', label: 'Curated sets' },
  { id: 'era', label: 'Eras' },
  { id: 'region', label: 'Regions' },
  { id: 'theme', label: 'Themes' },
  { id: 'type', label: 'Kinds' },
  { id: 'chronicles', label: 'Chronicles' },
  { id: 'battle-maps', label: 'Battle maps' },
];

/** Scroll to `#section` once the page has content (breadcrumbs link to
 *  `/browse#region`; the router does not scroll to hashes itself). */
function useScrollToHash(ready: boolean) {
  const { hash } = useLocation();
  useEffect(() => {
    if (!ready || !hash) return;
    document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView?.({ block: 'start' });
  }, [ready, hash]);
}

/** `/browse` (spec D4): curated sets, the era / region / theme / type grids,
 *  the leading chronicles and the battle maps. */
export function BrowseIndexPage() {
  useBrowseDocumentTitle(
    'Browse',
    'Browse History Mapped by curated set, era, region and theme, or open a chronicle or a battle map.',
  );
  const { tags, isLoading, isError, error, refetch } = useTags();
  const sections = useMemo(() => facetSections(tags), [tags]);
  useScrollToHash(!isLoading);

  return (
    <BrowseShell>
      <header className="max-w-3xl">
        <h1 className="font-heading text-4xl font-semibold tracking-tight sm:text-5xl">Browse</h1>
        <p className="mt-3 text-lg text-muted-foreground">
          Every chronicle, battle map, person, place and event in the atlas, by curated set, era, region and theme.
          Each has its own page, and the globe is always one click away.
        </p>
        <nav aria-label="On this page" className="mt-5 flex flex-wrap gap-1.5">
          {JUMPS.map((j) => (
            <a
              key={j.id}
              href={`#${j.id}`}
              className="rounded-full border bg-card px-3 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              {j.label}
            </a>
          ))}
        </nav>
      </header>

      <div className="mt-6">
        <CuratedSets />
        {isLoading && (
          <BrowseSection id="era" title="Eras">
            <CardSkeletons count={6} />
          </BrowseSection>
        )}
        {isError && (
          <BrowseSection id="era" title="Eras, regions and themes">
            <QueryNotice error={error} what="the tag vocabulary" onRetry={() => void refetch()} />
          </BrowseSection>
        )}
        {sections.map((s) => (
          <FacetGrid key={s.facet} section={s} />
        ))}
        <ChronicleStrip />
        <StoryStrip />
      </div>
    </BrowseShell>
  );
}
