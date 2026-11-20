import { History, ScrollText, Search } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { yearRangeLabel } from '@/app/routes/browse/browse-model';
import { GroupDot } from '@/components/atlas/GroupBadge';
import { StoryKindIcon, storyKindLabel } from '@/components/atlas/StoryCard';
import {
  useChronicleNav,
  useForYou,
  useOpenBrowseTab,
  useSearchFilter,
  useSelection,
  useStoryNav,
} from '@/hooks';
import { uniqueBy } from '@/lib/discover/pick';
import { clearRecents, recentEntityIds, useRecents } from '@/lib/discover/recents';
import type { Recents } from '@/lib/discover/recents';
import { becauseLine, relationLine } from '@/lib/discover/wording';
import { formatYear } from '@/lib/format';
import type { ForYou, ForYouEntity } from '@/lib/schemas/discover';
import { chronicleAtlasHref, searchAtlasHref, storyAtlasHref } from '@/lib/site-links';
import { cn } from '@/lib/utils';
import { DiscoverCard, GoTo } from './kit';
import type { DiscoverVariant } from './kit';
import { BattleMapMark } from './OnThisDayCard';

/** What a chronicle, battle-map or search row does: a link on a site page, a click in the atlas. */
type Act = { to: string } | { run: () => void };

interface Actions {
  chronicle: (slug: string) => Act;
  story: (slug: string) => Act;
  search: (word: string) => Act;
}

/** On a site page everything is a link into the atlas. */
const PAGE_ACTIONS: Actions = {
  chronicle: (slug) => ({ to: chronicleAtlasHref(slug) }),
  story: (slug) => ({ to: storyAtlasHref(slug) }),
  search: (word) => ({ to: searchAtlasHref(word) }),
};

function Go({
  act,
  className,
  title,
  children,
}: {
  act: Act;
  className?: string;
  title?: string;
  children: ReactNode;
}) {
  if ('to' in act) {
    return (
      <Link to={act.to} className={className} title={title}>
        {children}
      </Link>
    );
  }
  return (
    <button type="button" onClick={act.run} className={cn('text-left', className)} title={title}>
      {children}
    </button>
  );
}

const ROW = 'flex w-full min-w-0 items-start gap-2 rounded-md px-2 py-1.5 transition-colors hover:bg-muted/60';
const LABEL = 'px-2 pb-0.5 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase';
const SUB = 'block truncate text-[11px] text-muted-foreground';
const CHIP =
  'inline-flex max-w-full items-center gap-1 rounded-full border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground';

/**
 * A related entity: its name, then the year it opens at and how it is related
 * to the opened entity it comes from. Goes to it on the map in that year (the
 * year of the relationship, or the first year both existed: the API's `year`).
 */
function EntityRow({
  variant,
  entity,
  via,
}: {
  variant: DiscoverVariant;
  entity: ForYouEntity;
  /** The name of the opened entity it comes from. */
  via: string | null;
}) {
  const openAt = entity.year ?? entity.start_year;
  const year = openAt != null ? formatYear(openAt) : null;
  const why = relationLine(entity.relation, via, entity.outgoing);
  return (
    <li className="min-w-0">
      <GoTo
        variant={variant}
        target={{ id: entity.id, year: openAt }}
        title={entity.summary ? `${entity.name}: ${entity.summary}` : entity.name}
        className={ROW}
      >
        <GroupDot group={entity.entity_group} className={variant === 'page' ? 'mt-[6.5px]' : 'mt-[5.5px]'} />
        <span className="min-w-0 flex-1">
          <span className="flex min-w-0 items-center gap-1.5">
            <span className="min-w-0 truncate font-medium">{entity.name}</span>
            {entity.has_map_story && <BattleMapMark />}
          </span>
          {(year || why) && (
            <span className={SUB}>
              {year && <span className="font-mono">{year}</span>}
              {year && why && ' · '}
              {why}
            </span>
          )}
        </span>
      </GoTo>
    </li>
  );
}

function ChronicleRow({ chronicle: c, act }: { chronicle: ForYou['chronicles'][number]; act: Act }) {
  const range = yearRangeLabel(c.start_year, c.end_year);
  const steps = c.entry_count != null && c.entry_count > 0 ? `${c.entry_count} steps` : null;
  return (
    <li className="min-w-0">
      <Go act={act} title={`Start the tour: ${c.title}`} className={ROW}>
        <ScrollText size={14} aria-hidden className="mt-0.5 flex-none text-muted-foreground" />
        <span className="min-w-0 flex-1">
          <span className="line-clamp-2 font-medium">{c.title}</span>
          {(range || steps) && (
            <span className={SUB}>
              {range && <span className="font-mono">{range}</span>}
              {range && steps && ' · '}
              {steps}
            </span>
          )}
        </span>
      </Go>
    </li>
  );
}

function StoryRow({ story: s, act }: { story: ForYou['stories'][number]; act: Act }) {
  const meta = [
    storyKindLabel(s.kind),
    s.year != null ? formatYear(s.year) : null,
    s.step_count != null && s.step_count > 0 ? `${s.step_count} steps` : null,
  ].filter(Boolean);
  return (
    <li className="min-w-0">
      <Go act={act} title={`Play it on the map: ${s.title}`} className={ROW}>
        <span className="mt-px grid size-[18px] flex-none place-items-center rounded bg-amber-700 text-white">
          <StoryKindIcon kind={s.kind} size={11} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="line-clamp-2 font-medium">{s.title}</span>
          <span className={SUB}>{meta.join(' · ')}</span>
        </span>
      </Go>
    </li>
  );
}

/** How wide the related entities run on the page, by how many of the two other lists sit beside them. */
const ENTITY_SPAN = ['md:col-span-2 lg:col-span-4', 'md:col-span-2 lg:col-span-3', 'md:col-span-2'];
const ENTITY_COLUMNS = ['sm:grid-cols-2 lg:grid-cols-4', 'sm:grid-cols-2 lg:grid-cols-3', 'sm:grid-cols-2'];

function Skeleton({ variant }: { variant: DiscoverVariant }) {
  const page = variant === 'page';
  return (
    <DiscoverCard variant={variant} icon={History} title="For you">
      <div aria-hidden className="animate-pulse">
        <div className="h-3 w-3/5 rounded bg-muted/60" />
        <ul className={cn('mt-3', page ? 'grid gap-x-4 gap-y-2 sm:grid-cols-2 lg:grid-cols-4' : 'space-y-2')}>
          {Array.from({ length: page ? 16 : 5 }, (_, i) => (
            <li key={i} className="h-9 rounded bg-muted/60" />
          ))}
        </ul>
      </div>
    </DiscoverCard>
  );
}

/** The card itself, once there is something opened to ask about. */
function Suggestions({
  variant,
  recents,
  actions,
}: {
  variant: DiscoverVariant;
  recents: Recents;
  actions: Actions;
}) {
  const { data, isError } = useForYou(recentEntityIds(recents));
  if (!data) return isError ? null : <Skeleton variant={variant} />;

  const entities = uniqueBy(data.entities, (e) => e.id);
  const chronicles = uniqueBy(data.chronicles, (c) => c.chronicle_id);
  const stories = uniqueBy(data.stories, (s) => s.id);
  if (entities.length + chronicles.length + stories.length === 0) return null;

  const page = variant === 'page';
  const because = becauseLine(data.because.map((seed) => seed.name));
  const seeds = new Map(data.because.map((seed) => [seed.id, seed.name]));
  const beside = (chronicles.length > 0 ? 1 : 0) + (stories.length > 0 ? 1 : 0);

  return (
    <DiscoverCard
      variant={variant}
      icon={History}
      title="For you"
      footer={
        <span className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
          <span>From what you opened in this browser.</span>
          <button
            type="button"
            onClick={() => clearRecents()}
            title="Forget what was opened and searched in this browser"
            className="underline underline-offset-2 hover:text-foreground"
          >
            Clear
          </button>
        </span>
      }
    >
      {because && (
        <p className={cn('break-words text-muted-foreground', page ? 'text-sm' : 'text-[12px] leading-snug')}>
          {because}
        </p>
      )}

      <div
        className={cn(
          '-mx-2 mt-2',
          page ? 'grid gap-x-4 gap-y-3 text-sm md:grid-cols-2 lg:grid-cols-4' : 'space-y-3 text-[13px] leading-[18px]',
        )}
      >
        {entities.length > 0 && (
          <div className={cn('min-w-0', page && ENTITY_SPAN[beside])}>
            {page && <p className={LABEL}>Related</p>}
            <ul className={cn(page && 'grid gap-x-4', page && ENTITY_COLUMNS[beside])}>
              {entities.map((entity) => (
                <EntityRow
                  key={entity.id}
                  variant={variant}
                  entity={entity}
                  via={seeds.get(entity.via) ?? null}
                />
              ))}
            </ul>
          </div>
        )}
        {chronicles.length > 0 && (
          <div className="min-w-0">
            <p className={LABEL}>Chronicles</p>
            <ul>
              {chronicles.map((c) => (
                <ChronicleRow key={c.chronicle_id} chronicle={c} act={actions.chronicle(c.slug)} />
              ))}
            </ul>
          </div>
        )}
        {stories.length > 0 && (
          <div className="min-w-0">
            <p className={LABEL}>Battle maps</p>
            <ul>
              {stories.map((s) => (
                <StoryRow key={s.id} story={s} act={actions.story(s.slug)} />
              ))}
            </ul>
          </div>
        )}
      </div>

      {recents.searches.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-muted-foreground">Recent searches</span>
          {recents.searches.map((search) => (
            <Go
              key={search.q}
              act={actions.search(search.q)}
              title={`Search for “${search.q}” again`}
              className={CHIP}
            >
              <Search size={11} aria-hidden className="flex-none" />
              <span className="truncate">{search.q}</span>
            </Go>
          ))}
        </div>
      )}
    </DiscoverCard>
  );
}

/**
 * In the atlas the rows act in place: a chronicle starts its tour, a battle
 * map plays, a search word becomes the filter again (closing the open entity,
 * as the search box does: it would hold the map on its own relations).
 */
function PanelSuggestions({ recents }: { recents: Recents }) {
  const { enter: enterChronicle } = useChronicleNav();
  const { enter: enterStory } = useStoryNav();
  const { clear: clearSelection } = useSelection();
  const { setFilter } = useSearchFilter();
  const openTab = useOpenBrowseTab();
  const actions: Actions = {
    chronicle: (slug) => ({ run: () => enterChronicle(slug) }),
    story: (slug) => ({ run: () => enterStory(slug) }),
    search: (word) => ({
      run: () => {
        void clearSelection();
        void setFilter(word);
        // The matches are listed on the Entities tab.
        openTab('entities');
      },
    }),
  };
  return <Suggestions variant="panel" recents={recents} actions={actions} />;
}

/**
 * Entities, chronicles and battle maps related to what this browser opened
 * lately, with the recent searches to run again. Hidden until something has
 * been opened, and when the API has nothing to suggest. The list of opened
 * entities stays in this browser (`lib/discover/recents`); only their ids are
 * sent, to ask for the suggestions.
 */
export function ForYouCard({ variant }: { variant: DiscoverVariant }) {
  const recents = useRecents();
  if (recents.entities.length === 0) return null;
  return variant === 'panel' ? (
    <PanelSuggestions recents={recents} />
  ) : (
    <Suggestions variant="page" recents={recents} actions={PAGE_ACTIONS} />
  );
}
