import { ChevronDown, ChevronUp, Globe } from 'lucide-react';
import { useState } from 'react';
import { GroupDot } from '@/components/atlas/GroupBadge';
import { useMeanwhile } from '@/hooks';
import { MEANWHILE_PAGE_REGIONS, leadEvents, offYear, spread } from '@/lib/discover/pick';
import type { LeadEvents, RegionWithEvent } from '@/lib/discover/pick';
import { meanwhileRule, onTheMap, regionInSentence, sentenceName } from '@/lib/discover/wording';
import { formatYear } from '@/lib/format';
import type { DiscoverEntity, MeanwhileRegion } from '@/lib/schemas/discover';
import { cn } from '@/lib/utils';
import { DiscoverCard, GoTo } from './kit';
import type { DiscoverVariant } from './kit';
import { BattleMapMark } from './OnThisDayCard';

/** The years GET /discover/meanwhile answers for; any other is a 422. */
const FIRST_YEAR = -4000;

/** `year` as the whole year to ask for, or null when the API has no answer for it. */
function askable(year: number): number | null {
  if (!Number.isFinite(year)) return null;
  const whole = Math.trunc(year);
  return whole >= FIRST_YEAR && whole <= new Date().getFullYear() ? whole : null;
}

const cardTitle = (year?: number) => (year == null ? 'Meanwhile' : `Meanwhile in ${formatYear(year)}`);

/** Two columns of regions where the page card is wide (it is one grid column on a large screen). */
const PAGE_LIST = 'grid gap-x-4 gap-y-2 sm:grid-cols-2 lg:grid-cols-1';
/** A name inside running text that is a link. */
const TEXT_LINK =
  'font-medium text-foreground underline decoration-foreground/30 underline-offset-2 hover:decoration-foreground';
const QUIET_ACTION = 'text-muted-foreground underline-offset-2 hover:text-foreground hover:underline';

/**
 * One of a region's two lines: its event or its state. In the atlas it opens
 * the entity and leaves the timeline where the reader put it; from the page
 * the link also carries the card's year.
 */
function EntityLine({
  variant,
  what,
  entity,
  year,
}: {
  variant: DiscoverVariant;
  what: 'Event' | 'State';
  entity: DiscoverEntity;
  year: number;
}) {
  const page = variant === 'page';
  const off = what === 'Event' ? offYear(entity, year) : null;
  return (
    <GoTo
      variant={variant}
      target={page ? { id: entity.id, year } : { id: entity.id }}
      title={entity.summary ? `${entity.name}: ${entity.summary}` : entity.name}
      className={cn(
        'relative flex w-full min-w-0 items-center gap-2 rounded-md px-2 py-1 transition-colors hover:bg-muted/60',
        page ? 'text-sm' : 'text-[13px] leading-[18px]',
      )}
    >
      <GroupDot group={entity.entity_group} />
      <span className="sr-only">{what}: </span>
      <span className="flex min-w-0 flex-1 items-center gap-1.5">
        <span className={cn('min-w-0 truncate', what === 'Event' && 'font-medium')}>{entity.name}</span>
        {entity.has_map_story && <BattleMapMark />}
      </span>
      {off != null && (
        <span className="flex-none font-mono text-[11px] text-muted-foreground tabular-nums">{formatYear(off)}</span>
      )}
    </GoTo>
  );
}

function Region({ variant, region, year }: { variant: DiscoverVariant; region: MeanwhileRegion; year: number }) {
  return (
    <li className="min-w-0">
      <p
        title={onTheMap(region.counts) ?? undefined}
        className="truncate px-2 pb-0.5 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase"
      >
        {region.name}
      </p>
      {region.event && <EntityLine variant={variant} what="Event" entity={region.event} year={year} />}
      {region.polity && <EntityLine variant={variant} what="State" entity={region.polity} year={year} />}
    </li>
  );
}

/** An event's name inside the lead sentence. A link on the page; in the atlas its row below is the way in. */
function LeadEvent({ variant, region, year }: { variant: DiscoverVariant; region: RegionWithEvent; year: number }) {
  const { event } = region;
  const { article, name } = sentenceName(event);
  const off = offYear(event, year);
  return (
    <>
      {article}
      {variant === 'page' ? (
        <GoTo variant="page" target={{ id: event.id, year }} className={TEXT_LINK}>
          {name}
        </GoTo>
      ) : (
        <span className="font-medium text-foreground">{name}</span>
      )}
      {off != null && ` (${formatYear(off)})`}
    </>
  );
}

/**
 * The lead sentence: two regions far apart, set side by side. "While … in A,
 * … in B" when both events were under way in the card's year; when they are
 * from the years around it, "Around …" and each event's own year.
 */
function Lead({ variant, lead, year }: { variant: DiscoverVariant; lead: LeadEvents; year: number }) {
  const [west, east] = lead.pair;
  const first = <LeadEvent variant={variant} region={west} year={year} />;
  const second = <LeadEvent variant={variant} region={east} year={year} />;
  return (
    <p
      className={cn(
        'mt-2 break-words text-foreground/80',
        variant === 'page' ? 'text-sm' : 'text-[13px] leading-snug',
      )}
    >
      {lead.sameYear ? (
        <>
          While {first} took place in {regionInSentence(west)}, {second} took place in {regionInSentence(east)}.
        </>
      ) : (
        <>
          Around {formatYear(year)}, {first} took place in {regionInSentence(west)} and {second} took place in{' '}
          {regionInSentence(east)}.
        </>
      )}
    </p>
  );
}

/** The card's outline while its year loads (on the page, while the year itself is still unknown). */
export function MeanwhileSkeleton({ variant, year }: { variant: DiscoverVariant; year?: number }) {
  const page = variant === 'page';
  return (
    <DiscoverCard variant={variant} icon={Globe} title={cardTitle(year)}>
      <div aria-hidden className="animate-pulse">
        <div className="h-3 w-2/3 rounded bg-muted/60" />
        <div className="mt-3 h-10 rounded bg-muted/60" />
        <ul className={cn('mt-3', page ? PAGE_LIST : 'space-y-2')}>
          {Array.from({ length: page ? MEANWHILE_PAGE_REGIONS : 6 }, (_, i) => (
            <li key={i} className="space-y-1.5 py-0.5">
              <div className="h-2.5 w-24 rounded bg-muted/60" />
              <div className="h-[18px] rounded bg-muted/60" />
              <div className="h-[18px] w-4/5 rounded bg-muted/60" />
            </li>
          ))}
        </ul>
      </div>
    </DiscoverCard>
  );
}

/**
 * One year across the map: per world region, its most notable event around
 * then and its most notable state. It only sets them side by side.
 *
 * In the atlas (`panel`) the year is the timeline's and the last answer stays
 * on screen, dimmed, while the next loads. On the browse page (`page`) the
 * year is given with a `reason` ("The year of …"), and a few regions show
 * until the reader asks for all. Not rendered when the API has no answer.
 */
export function MeanwhileCard({
  variant,
  year,
  reason,
}: {
  variant: DiscoverVariant;
  year: number;
  /** Why this year, shown under the title on the browse page. */
  reason?: string;
}) {
  const asked = askable(year);
  const { data, isError, isPlaceholderData } = useMeanwhile(asked);
  const [all, setAll] = useState(false);

  if (asked === null) return null;
  if (!data) return isError ? null : <MeanwhileSkeleton variant={variant} year={asked} />;
  if (data.regions.length === 0) return null;

  const page = variant === 'page';
  const regions = page && !all ? spread(data.regions, MEANWHILE_PAGE_REGIONS) : data.regions;
  const lead = leadEvents(data.regions, data.year);
  const note = [reason, onTheMap(data.totals)].filter(Boolean).join(' · ');

  return (
    <DiscoverCard
      variant={variant}
      icon={Globe}
      title={cardTitle(data.year)}
      footer={meanwhileRule(data.window)}
      className={cn('transition-opacity', isPlaceholderData && 'opacity-60')}
    >
      {note && <p className={cn('break-words text-muted-foreground', page ? 'text-xs' : 'text-[11px]')}>{note}</p>}
      {lead && <Lead variant={variant} lead={lead} year={data.year} />}
      <ul className={cn('-mx-2 mt-3', page ? PAGE_LIST : 'space-y-2')}>
        {regions.map((region) => (
          <Region key={region.key} variant={variant} region={region} year={data.year} />
        ))}
      </ul>
      {page && data.regions.length > MEANWHILE_PAGE_REGIONS && (
        <button
          type="button"
          onClick={() => setAll((shown) => !shown)}
          aria-expanded={all}
          className={cn('mt-2 inline-flex items-center gap-1 text-xs', QUIET_ACTION)}
        >
          {all ? 'Show fewer regions' : `Show all ${data.regions.length} regions`}
          {all ? <ChevronUp size={13} aria-hidden /> : <ChevronDown size={13} aria-hidden />}
        </button>
      )}
    </DiscoverCard>
  );
}
