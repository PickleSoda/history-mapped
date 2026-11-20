import { ArrowRight, ArrowUp, Check, Clock, Compass, Copy, MapPin, Navigation } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { buttonVariants } from '@/components/ui/button';
import { useAtlasGo, useDailyQuest, useMapInstance } from '@/hooks';
import {
  clueText,
  COMPASS_WORDS,
  expeditionName,
  kmText,
  MAX_STARS,
  NO_PROGRESS,
  shareText,
  standingStreak,
  starsFor,
  tally,
  targetSpan,
} from '@/lib/discover/quest';
import type { TargetProgress, TargetsProgress } from '@/lib/discover/quest';
import { flyToTarget } from '@/lib/discover/quest-map';
import { useQuestDay, useQuestLive, useQuestStore } from '@/lib/discover/quest-store';
import { formatYear } from '@/lib/format';
import type { Quest, QuestDifficulty, QuestTarget } from '@/lib/schemas/discover';
import { browsePath, todayAtlasHref } from '@/lib/site-links';
import { cn } from '@/lib/utils';
import { useEphemeralStore } from '@/stores/ephemeral';
import { DiscoverCard, GoTo } from './kit';
import type { DiscoverVariant } from './kit';
import { PlaceMeter, Stars, TimeMeter, YearsHidden } from './QuestMeter';

/** The meters' colour for "here", on the ticks that mark an arrival or a find. */
const THERE = 'text-[#199e70]';
const SMALL_BUTTON =
  'inline-flex flex-none items-center gap-1 rounded-md border bg-card px-2 py-1 text-[11px] font-medium transition-colors hover:bg-muted';

/** Today's expedition, once it has loaded and has targets. */
function useTodaysQuest(): { quest: Quest | null; loading: boolean; today: string } {
  const today = useQuestDay();
  const { data, isPending } = useDailyQuest(today);
  return { quest: data && data.targets.length > 0 ? data : null, loading: isPending, today };
}

/** The card's outline while the day's expedition loads: its frame and three quiet rows. */
function QuestSkeleton({ variant }: { variant: DiscoverVariant }) {
  return (
    <DiscoverCard variant={variant} icon={Compass} title="Expedition">
      <ul aria-hidden className="space-y-2 motion-safe:animate-pulse">
        {[0, 1, 2].map((row) => (
          <li key={row} className={cn('rounded bg-muted/60', variant === 'page' ? 'h-9' : 'h-8')} />
        ))}
      </ul>
    </DiscoverCard>
  );
}

function Difficulty({ level }: { level: QuestDifficulty }) {
  return (
    <span className="flex-none rounded-full border px-1.5 py-px text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
      {level}
    </span>
  );
}

function streakLabel(days: number): string | undefined {
  return days > 0 ? `${days}-day streak` : undefined;
}

function foundLabel(count: number): string {
  return count === 3 ? 'All three found' : 'All found';
}

/** "1868 CE", or the span for a target that lasted years. */
function whenText(target: QuestTarget): string {
  const [start, end] = targetSpan(target);
  return start === end ? formatYear(start) : `${formatYear(start)} – ${formatYear(end)}`;
}

// ── in the atlas: the playable card ───────────────────────────────────────────

/** The "where" hint: the region, the place when the atlas names one, and the way there from the middle of the map. */
function WhereHint({ target }: { target: QuestTarget }) {
  const km = useQuestLive((s) => (s.reading?.id === target.id ? s.reading.km : null));
  const compass = useQuestLive((s) => (s.reading?.id === target.id ? s.reading.compass : null));
  const arrow = useQuestLive((s) => (s.reading?.id === target.id ? s.reading.arrow : null));
  const names = [target.region, target.place].filter(Boolean).join(' · ');
  return (
    <div className="space-y-1 pl-0.5 text-muted-foreground">
      {names && (
        <p className="flex items-start gap-1.5">
          <MapPin size={12} aria-hidden className="mt-0.5 flex-none" />
          <span className="min-w-0 break-words text-foreground">{names}</span>
        </p>
      )}
      {km != null && (
        <p className="flex items-start gap-1.5" title="Measured from the middle of the map">
          <ArrowUp
            size={12}
            aria-hidden
            className={cn('mt-0.5 flex-none', (compass == null || arrow == null) && 'invisible')}
            style={{ transform: `rotate(${(arrow ?? 0) * 45}deg)` }}
          />
          <span className="min-w-0">
            {compass ? `${kmText(km)} to the ${COMPASS_WORDS[compass]}` : 'Under the middle of the map'}
          </span>
        </p>
      )}
    </div>
  );
}

/** The target being looked for: its clue, how warm the reader is, the hints and what they cost. */
function ActiveTarget({ target }: { target: QuestTarget }) {
  const progress = useQuestStore((s) => s.targets[target.id]) ?? NO_PROGRESS;
  const hint = useQuestStore((s) => s.hint);
  const take = useQuestStore((s) => s.take);
  const stop = useQuestStore((s) => s.stop);
  const arrived = useQuestLive((s) => s.reading?.id === target.id && s.reading.arrived);
  const go = useAtlasGo();
  const { map } = useMapInstance();
  const showWhen = progress.when || progress.taken;
  const showWhere = progress.where || progress.taken;

  const takeThere = () => {
    take(target.id);
    // The timeline through the URL; the flight is the expedition's own, so
    // that it ends close enough to count as there on any size of window.
    go({ year: target.year });
    if (map) flyToTarget(map, useEphemeralStore.getState().mapInsets, target.at);
  };

  return (
    <li className="rounded-lg border bg-muted/40 p-2.5">
      <div className="flex items-start gap-2">
        <p className="min-w-0 flex-1 text-[13px] leading-snug font-semibold break-words">
          <YearsHidden text={clueText(target.name, target, progress)} />
        </p>
        <Difficulty level={target.difficulty} />
      </div>
      {target.summary && (
        <p className="mt-1 text-[12px] leading-snug break-words text-muted-foreground">
          <YearsHidden text={clueText(target.summary, target, progress)} />
        </p>
      )}

      <div className="mt-2.5 space-y-1.5 text-[12px]">
        <div className="flex min-h-6 items-center justify-between gap-2">
          <TimeMeter id={target.id} />
          {!showWhen && (
            <button
              type="button"
              onClick={() => hint(target.id, 'when')}
              className={SMALL_BUTTON}
              aria-label="When hint: show the year"
              title="Show the year (costs a star)"
            >
              Hint
            </button>
          )}
        </div>
        {showWhen && (
          <p className="flex items-center gap-1.5 pl-0.5 font-mono text-[12px]">
            <Clock size={12} aria-hidden className="flex-none text-muted-foreground" />
            {whenText(target)}
          </p>
        )}
        <div className="flex min-h-6 items-center justify-between gap-2">
          <PlaceMeter id={target.id} />
          {!showWhere && (
            <button
              type="button"
              onClick={() => hint(target.id, 'where')}
              className={SMALL_BUTTON}
              aria-label="Where hint: show the region and the way there"
              title="Show the region and the way there (costs a star)"
            >
              Hint
            </button>
          )}
        </div>
        {showWhere && <WhereHint target={target} />}
      </div>

      {arrived && (
        <p role="status" className="mt-2.5 flex items-start gap-1.5 rounded-md bg-[#199e70]/12 px-2 py-1.5 text-[12px] font-medium">
          <Check size={13} strokeWidth={3} aria-hidden className={cn('mt-0.5 flex-none', THERE)} />
          Right place, right time. Click the ring on the map.
        </p>
      )}

      <div className="mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1.5">
        <span
          className="flex flex-1 items-center gap-1 text-[11px] text-muted-foreground"
          title="The stars for finding it now"
        >
          Worth <Stars count={starsFor(progress)} />
        </span>
        <button type="button" onClick={takeThere} className={SMALL_BUTTON} title="Go to its year and place (no stars)">
          <Navigation size={11} aria-hidden />
          Take me there
        </button>
        <button type="button" onClick={stop} className={SMALL_BUTTON}>
          Stop
        </button>
      </div>
      <p className="mt-1.5 text-[11px] leading-snug text-muted-foreground">
        {progress.taken
          ? 'You were taken there, so no stars this time. Finding it still counts.'
          : 'The meters read the year on the timeline and the middle of the map. A hint costs a star; being taken there earns none.'}
      </p>
    </li>
  );
}

/** A target already found: its stars and its summary; it opens again on the map at its year. */
function FoundTarget({ target, stars }: { target: QuestTarget; stars: number }) {
  return (
    <li className="-mx-2">
      <GoTo
        variant="panel"
        target={{ id: target.id, year: target.year }}
        className="flex w-full items-start gap-2 rounded-lg px-2 py-1.5 transition-colors hover:bg-muted/60"
        title="Open it on the map"
      >
        <Check size={14} strokeWidth={3} aria-hidden className={cn('mt-0.5 flex-none', THERE)} />
        <span className="min-w-0 flex-1">
          <span className="flex items-start gap-2">
            <span className="min-w-0 flex-1 text-[13px] leading-snug font-medium break-words">{target.name}</span>
            <Stars count={stars} className="mt-0.5" />
          </span>
          {target.summary && (
            <span className="mt-0.5 line-clamp-3 text-[12px] leading-snug break-words text-muted-foreground">
              {target.summary}
            </span>
          )}
        </span>
      </GoTo>
    </li>
  );
}

/** A target not being looked for (yet, or any more). */
function WaitingTarget({ target, progress }: { target: QuestTarget; progress: TargetProgress | undefined }) {
  const start = useQuestStore((s) => s.start);
  return (
    <li className="-mx-2 flex items-center gap-2 rounded-lg px-2 py-1.5">
      <span className="min-w-0 flex-1">
        <span className="block text-[13px] leading-snug font-medium break-words">
          <YearsHidden text={clueText(target.name, target, progress)} />
        </span>
        <span className="mt-1 flex">
          <Difficulty level={target.difficulty} />
        </span>
      </span>
      <button
        type="button"
        onClick={() => start(target.id)}
        className={cn(buttonVariants({ variant: 'outline', size: 'xs' }), 'flex-none')}
      >
        Start
      </button>
    </li>
  );
}

/** The day is done: the stars and the result to copy (stars only, no names). */
function Done({ quest, targets, stars }: { quest: Quest; targets: TargetsProgress; stars: number }) {
  const [copy, setCopy] = useState<'idle' | 'copied' | 'failed'>('idle');
  const [text, setText] = useState('');
  const fallback = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (copy !== 'copied') return;
    const timer = setTimeout(() => setCopy('idle'), 2500);
    return () => clearTimeout(timer);
  }, [copy]);
  // The clipboard was refused: show the text selected, ready to copy by hand.
  useEffect(() => {
    if (copy === 'failed') fallback.current?.select();
  }, [copy]);

  const copyResult = async () => {
    const result = shareText(
      quest.number,
      quest.targets.map((t) => ({ difficulty: t.difficulty, stars: starsFor(targets[t.id] ?? NO_PROGRESS) })),
      `${window.location.origin}${browsePath()}`,
    );
    setText(result);
    try {
      await navigator.clipboard.writeText(result);
      setCopy('copied');
    } catch {
      setCopy('failed');
    }
  };

  return (
    <div className="mb-2.5 rounded-lg bg-muted/50 p-2.5">
      <p className="flex items-center gap-1.5 text-[13px] font-semibold">
        <Check size={14} strokeWidth={3} aria-hidden className={cn('flex-none', THERE)} />
        {foundLabel(quest.targets.length)}
      </p>
      <p className="mt-0.5 text-[12px] text-muted-foreground">
        {stars} of {quest.targets.length * MAX_STARS} stars. A new expedition tomorrow.
      </p>
      <div className="mt-2 flex items-center gap-2">
        <button type="button" onClick={() => void copyResult()} className={SMALL_BUTTON}>
          <Copy size={11} aria-hidden />
          Copy result
        </button>
        <span role="status" className="text-[11px] text-muted-foreground">
          {copy === 'copied' ? 'Copied' : copy === 'failed' ? 'Copy it from here:' : ''}
        </span>
      </div>
      {copy === 'failed' && (
        <textarea
          ref={fallback}
          readOnly
          rows={quest.targets.length + 2}
          value={text}
          aria-label="Your result"
          className="mt-2 block w-full resize-none rounded-md border bg-card p-2 font-mono text-[11px] leading-snug"
        />
      )}
    </div>
  );
}

function QuestPanel() {
  const { quest, loading, today } = useTodaysQuest();
  const active = useQuestStore((s) => s.active);
  const targets = useQuestStore((s) => s.targets);
  const streak = useQuestStore((s) => s.streak);
  if (loading) return <QuestSkeleton variant="panel" />;
  if (!quest) return null;

  const day = tally(
    quest.targets.map((t) => t.id),
    targets,
  );
  return (
    <DiscoverCard
      variant="panel"
      icon={Compass}
      title={expeditionName(quest.number)}
      aside={streakLabel(standingStreak(streak, today))}
    >
      {day.complete ? (
        <Done quest={quest} targets={targets} stars={day.stars} />
      ) : (
        day.found === 0 &&
        active == null && (
          <p className="mb-2 text-[12px] leading-snug text-muted-foreground">
            Three places and times to find on the map. Start one, then move the timeline and the map.
          </p>
        )
      )}
      <ol className="space-y-1">
        {quest.targets.map((target) => {
          const progress = targets[target.id];
          if (progress?.found) return <FoundTarget key={target.id} target={target} stars={starsFor(progress)} />;
          if (target.id === active) return <ActiveTarget key={target.id} target={target} />;
          return <WaitingTarget key={target.id} target={target} progress={progress} />;
        })}
      </ol>
    </DiscoverCard>
  );
}

// ── on the browse page: a teaser ──────────────────────────────────────────────

function QuestTeaser() {
  const { quest, loading, today } = useTodaysQuest();
  const active = useQuestStore((s) => s.active);
  const targets = useQuestStore((s) => s.targets);
  const streak = useQuestStore((s) => s.streak);
  if (loading) return <QuestSkeleton variant="page" />;
  if (!quest) return null;

  const ids = quest.targets.map((t) => t.id);
  const day = tally(ids, targets);
  const started = active != null || ids.some((id) => targets[id] != null);
  return (
    <DiscoverCard
      variant="page"
      icon={Compass}
      title={expeditionName(quest.number)}
      aside={streakLabel(standingStreak(streak, today))}
      footer={
        <Link to={todayAtlasHref()} className={buttonVariants({ size: 'sm' })}>
          {day.complete ? 'See it in the atlas' : started ? 'Continue in the atlas' : 'Start in the atlas'}
          <ArrowRight aria-hidden />
        </Link>
      }
    >
      <p className="text-sm text-muted-foreground">
        Three places and times to find on the map. Move the timeline and the map, and two meters tell you how warm
        you are.
      </p>
      <ul className="mt-3 space-y-2">
        {quest.targets.map((target) => {
          const progress = targets[target.id];
          return (
            <li key={target.id} className="flex items-start gap-2 text-sm">
              <span className="min-w-0 flex-1 leading-snug font-medium break-words">
                <YearsHidden text={clueText(target.name, target, progress)} />
              </span>
              {progress?.found && <Stars count={starsFor(progress)} size={14} className="mt-0.5" />}
              <Difficulty level={target.difficulty} />
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-sm text-muted-foreground">
        {day.complete
          ? `${foundLabel(ids.length)}: ${day.stars} of ${ids.length * MAX_STARS} stars.`
          : day.found > 0
            ? `${day.found} of ${ids.length} found, ${day.stars} ${day.stars === 1 ? 'star' : 'stars'} so far.`
            : started
              ? 'Started, nothing found yet.'
              : 'Not started yet today.'}
      </p>
    </DiscoverCard>
  );
}

/**
 * The daily expedition as a card: in the atlas (`panel`) the playable quest
 * (the three targets, the clue and the warmth of the one being looked for, the
 * hints, the stars and the streak); on the browse page (`page`) a teaser with
 * today's progress and a link into the atlas's Today tab. Renders nothing
 * when there is no expedition to show (the endpoint is missing, or empty).
 */
export function QuestCard({ variant }: { variant: DiscoverVariant }) {
  return variant === 'page' ? <QuestTeaser /> : <QuestPanel />;
}
