/**
 * The daily expedition's small visual pieces, shared by its card and by the
 * strip over the map: the five-step warmth meter (alone, and wired to the live
 * reading in time and in place), the stars, and a clue with its years left out.
 */
import { ArrowLeft, ArrowRight, Check, Star, ZoomIn } from 'lucide-react';
import { Fragment } from 'react';
import type { ReactNode } from 'react';
import { HIDDEN_YEAR, MAX_STARS, warmthSteps } from '@/lib/discover/quest';
import type { Warmth } from '@/lib/discover/quest';
import { useQuestLive } from '@/lib/discover/quest-store';
import { cn } from '@/lib/utils';

/**
 * The meter's colours. The number of filled steps and the word beside them
 * carry the level; the colour only says which side of "close" the reader is
 * on: blue far (cold, cool), orange near (warm, hot), green there. Three hues
 * that stay apart for colour-blind readers and stand out from both card
 * backgrounds (light, then dark); the empty steps are a tint of the same hue.
 */
const TONES = {
  far: { fill: 'bg-[#2a78d6] dark:bg-[#3987e5]', rest: 'bg-[#2a78d6]/20 dark:bg-[#3987e5]/25' },
  near: { fill: 'bg-[#eb6834] dark:bg-[#d95926]', rest: 'bg-[#eb6834]/20 dark:bg-[#d95926]/25' },
  here: { fill: 'bg-[#199e70]', rest: 'bg-[#199e70]/20' },
  unknown: { fill: 'bg-muted-foreground/25', rest: 'bg-muted-foreground/25' },
} as const;

const TONE: Record<Warmth, keyof typeof TONES> = {
  cold: 'far',
  cool: 'far',
  warm: 'near',
  hot: 'near',
  here: 'here',
};

const STEPS = [1, 2, 3, 4, 5];

/**
 * "When ▂▃▅ warm": a label, five rising steps filled up to the warmth, and
 * the word. `children` follow the word (which way to go, a cue). A null
 * warmth (the map is not ready) shows an empty meter.
 */
export function WarmthMeter({
  label,
  warmth,
  className,
  children,
}: {
  label: string;
  warmth: Warmth | null;
  className?: string;
  children?: ReactNode;
}) {
  const filled = warmth ? warmthSteps(warmth) : 0;
  const tone = TONES[warmth ? TONE[warmth] : 'unknown'];
  return (
    <span className={cn('inline-flex items-center gap-1.5 whitespace-nowrap', className)}>
      <span className="text-muted-foreground">{label}</span>
      <span aria-hidden className="flex items-end gap-[2px]">
        {STEPS.map((step) => (
          <i
            key={step}
            className={cn('w-1 rounded-[1px]', step <= filled ? tone.fill : tone.rest)}
            style={{ height: 3 + step * 2 }}
          />
        ))}
      </span>
      <span className="inline-flex min-w-[2.6em] items-center gap-0.5 font-semibold">
        {warmth ?? '…'}
        {warmth === 'here' && <Check size={12} strokeWidth={3} aria-hidden className="text-[#199e70]" />}
      </span>
      {children}
    </span>
  );
}

const CUE = 'inline-flex items-center gap-0.5 text-muted-foreground';

/** How warm the timeline is for target `id`, and which way its years lie. */
export function TimeMeter({ id, className }: { id: string; className?: string }) {
  const warmth = useQuestLive((s) => (s.reading?.id === id ? s.reading.time : null));
  const direction = useQuestLive((s) => (s.reading?.id === id ? s.reading.direction : null));
  return (
    <WarmthMeter label="When" warmth={warmth} className={className}>
      {warmth !== 'here' && direction === 'earlier' && (
        <span className={CUE}>
          <ArrowLeft size={11} aria-hidden />
          earlier
        </span>
      )}
      {warmth !== 'here' && direction === 'later' && (
        <span className={CUE}>
          later
          <ArrowRight size={11} aria-hidden />
        </span>
      )}
    </WarmthMeter>
  );
}

/** How warm the middle of the map is for target `id`. */
export function PlaceMeter({ id, className }: { id: string; className?: string }) {
  const warmth = useQuestLive((s) => (s.reading?.id === id ? s.reading.place : null));
  const zoomIn = useQuestLive((s) => s.reading?.id === id && s.reading.zoomIn);
  return (
    <WarmthMeter label="Where" warmth={warmth} className={className}>
      {zoomIn && (
        <span className={CUE}>
          <ZoomIn size={11} aria-hidden />
          zoom in
        </span>
      )}
    </WarmthMeter>
  );
}

/** Stars earned (or still to win) out of three. */
export function Stars({
  count,
  of = MAX_STARS,
  size = 12,
  className,
}: {
  count: number;
  of?: number;
  size?: number;
  className?: string;
}) {
  return (
    <span
      role="img"
      aria-label={`${count} of ${of} stars`}
      className={cn('inline-flex flex-none items-center gap-px', className)}
    >
      {Array.from({ length: of }, (_, i) => (
        <Star
          key={i}
          size={size}
          aria-hidden
          className={i < count ? 'fill-event text-event' : 'text-muted-foreground/40'}
        />
      ))}
    </span>
  );
}

/**
 * A name or a clue whose years were left out (`hideYears`): each gap is drawn
 * as a small blank, read out as "year hidden".
 */
export function YearsHidden({ text }: { text: string }) {
  const parts = text.split(HIDDEN_YEAR);
  if (parts.length === 1) return <>{text}</>;
  return (
    <>
      {parts.map((part, i) => (
        <Fragment key={i}>
          {i > 0 && (
            <span
              role="img"
              aria-label="year hidden"
              title="The year stays hidden until you find it or ask for it"
              className="mx-px inline-block h-[0.72em] w-[2em] rounded-[2px] bg-muted-foreground/30"
            />
          )}
          {part}
        </Fragment>
      ))}
    </>
  );
}
