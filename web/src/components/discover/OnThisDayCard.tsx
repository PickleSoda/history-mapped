import { CalendarDays, Swords } from 'lucide-react';
import { GroupDot } from '@/components/atlas/GroupBadge';
import { useOnThisDay } from '@/hooks';
import { dayMonthLabel } from '@/lib/discover/date';
import { ON_THIS_DAY_ROWS } from '@/lib/discover/pick';
import { useToday } from '@/lib/discover/today';
import { dayKeyLabel, kindWord, storedDayLabel, withoutOpeningAside } from '@/lib/discover/wording';
import { formatYear } from '@/lib/format';
import type { OnThisDayItem } from '@/lib/schemas/discover';
import { cn } from '@/lib/utils';
import { DiscoverCard, GoTo } from './kit';
import type { DiscoverVariant } from './kit';

/** The small crossed swords beside a name: it has a step-by-step battle map. */
export function BattleMapMark({ className }: { className?: string }) {
  return (
    <span title="Has a battle map" className={cn('relative flex-none text-amber-700 dark:text-amber-400', className)}>
      <Swords size={13} aria-hidden />
      <span className="sr-only">, has a battle map</span>
    </span>
  );
}

/** One thing that happened: its year, its name and what the day marks for it. */
function Row({ item, variant, showDay }: { item: OnThisDayItem; variant: DiscoverVariant; showDay: boolean }) {
  const page = variant === 'page';
  const word = kindWord(item.kind);
  const day = showDay ? storedDayLabel(item.date) : null;
  const text = page ? 'text-sm' : 'text-[13px] leading-[18px]';
  return (
    <li className="min-w-0">
      <GoTo
        variant={variant}
        target={{ id: item.id, year: item.year }}
        title={`${item.name}: show it on the map in ${formatYear(item.year)}`}
        className={cn(
          'flex w-full min-w-0 items-start gap-2 rounded-md px-2 transition-colors hover:bg-muted/60',
          page ? 'py-2' : 'py-1.5',
        )}
      >
        <span
          className={cn(
            'w-[60px] flex-none font-mono text-[11px] whitespace-nowrap text-muted-foreground tabular-nums',
            page ? 'leading-5' : 'leading-[18px]',
          )}
        >
          {formatYear(item.year)}
        </span>
        <GroupDot group={item.entity_group} className={page ? 'mt-[6.5px]' : 'mt-[5.5px]'} />
        <span className="min-w-0 flex-1">
          <span className="flex min-w-0 items-center gap-1.5">
            <span className={cn('min-w-0 truncate font-medium', text)}>{item.name}</span>
            {word && <span className={cn('flex-none text-muted-foreground', text)}>{word}</span>}
            {item.has_map_story && <BattleMapMark />}
          </span>
          {day && <span className="block truncate text-[11px] text-muted-foreground">{day}</span>}
          {page && item.summary && (
            <span className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
              {item.entity_type === 'person' ? withoutOpeningAside(item.summary) : item.summary}
            </span>
          )}
        </span>
      </GoTo>
    </li>
  );
}

/** Two columns of rows where the page card is wide (it is one grid column on a large screen). */
const PAGE_LIST = 'grid gap-x-4 sm:grid-cols-2 lg:grid-cols-1';

function Skeleton({ variant, date }: { variant: DiscoverVariant; date: string }) {
  const page = variant === 'page';
  return (
    <DiscoverCard variant={variant} icon={CalendarDays} title="On this day" aside={dayKeyLabel(date)}>
      <ul aria-hidden className={cn('-mx-2 animate-pulse', page && PAGE_LIST)}>
        {Array.from({ length: ON_THIS_DAY_ROWS[variant] }, (_, i) => (
          <li key={i} className={cn('px-2', page ? 'py-1.5' : 'py-1')}>
            <div className={cn('rounded bg-muted/60', page ? 'h-[54px]' : 'h-[22px]')} />
          </li>
        ))}
      </ul>
    </DiscoverCard>
  );
}

/**
 * What happened on today's month and day: an event, a founding, a birth, a
 * death. Each row goes to the entity on the map in its own year. Not rendered
 * when the API has no answer.
 */
export function OnThisDayCard({ variant }: { variant: DiscoverVariant }) {
  const today = useToday();
  const { data, isError } = useOnThisDay(today);
  if (!data) return isError ? null : <Skeleton variant={variant} date={today} />;

  const rows = data.items.slice(0, ON_THIS_DAY_ROWS[variant]);
  if (rows.length === 0) return null;
  const widened = data.widened > 0;

  return (
    <DiscoverCard
      variant={variant}
      icon={CalendarDays}
      title="On this day"
      aside={dayMonthLabel(data.month, data.day)}
      footer={widened ? 'Includes nearby days: little is dated to this one.' : undefined}
    >
      <ul className={cn('-mx-2', variant === 'page' && PAGE_LIST)}>
        {rows.map((item) => (
          <Row key={`${item.id}:${item.kind}`} item={item} variant={variant} showDay={widened} />
        ))}
      </ul>
    </DiscoverCard>
  );
}
