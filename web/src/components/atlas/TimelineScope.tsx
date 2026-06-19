import { Timescope } from '@timescope/react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { TimelineGantt } from '@/components/atlas/TimelineGantt';
import { useLiveScrub, useTimeState } from '@/hooks';
import { eraFor, formatYear, instantYear } from '@/lib/format';
import { APP_FONT_FAMILY } from '@/lib/timeline/theme';
import { AXIS_MAX, AXIS_MIN, clampYear, toYear } from '@/lib/timeline/year';

const TRACK = 'main';
const BAR_PX = 56;

/** Stable identities so the @timescope/react effects don't re-fire each render. */
const TIME_RANGE: [number, number] = [AXIS_MIN, AXIS_MAX];
const EMPTY = {};
const TRACKS = {
  [TRACK]: {
    timeAxis: {
      labels: { fontFamily: APP_FONT_FAMILY },
      timeFormat: (opts: { time: { number(): number } }) =>
        formatYear(Math.round(opts.time.number())),
    },
  },
};

/**
 * Bottom timeline — a simple timescope scrubber (date axis + draggable playhead).
 * The chevron opens the historical-periods gantt in a panel above the bar.
 *
 * Flicker fix: timescope's *programmatic* setTime (from a chronicle step or the
 * TopBar) animates the playhead and emits `timechanged` with intermediate frame
 * values. Committing those back to the URL caused the time state to oscillate.
 * We therefore only honour the time callbacks while the user is actually
 * pointer-dragging the canvas (`scrubbingRef`); programmatic changes are ignored.
 */
export function TimelineScope() {
  const { time } = useTimeState();
  const { liveScrub, setLiveScrub, commit } = useLiveScrub();
  const committedYear = instantYear(time);
  const displayYear = liveScrub ?? committedYear;
  const [ganttOpen, setGanttOpen] = useState(false);

  const scrubbingRef = useRef(false);
  useEffect(() => {
    // Clear after the release's synchronous `timechanged` has been handled, so a
    // real drag still commits but later animation frames do not.
    const end = () => setTimeout(() => (scrubbingRef.current = false), 0);
    window.addEventListener('pointerup', end);
    window.addEventListener('pointercancel', end);
    return () => {
      window.removeEventListener('pointerup', end);
      window.removeEventListener('pointercancel', end);
    };
  }, []);

  return (
    <div className="relative flex flex-col-reverse md:flex-row">
      {ganttOpen && (
        <div className="absolute inset-x-0 top-full z-20 border-b bg-card shadow-lg md:bottom-full md:top-auto md:border-b-0 md:border-t">
          <TimelineGantt />
        </div>
      )}

      {/* Readout + open/close button — left column on desktop, bottom row on mobile. */}
      <div className="flex flex-none flex-row items-center justify-between gap-2 px-4 py-1 md:w-[150px] md:flex-col md:items-start md:justify-center md:py-0">
        <div className="leading-tight">
          <div className="font-mono text-sm tabular-nums">{formatYear(displayYear)}</div>
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
            {eraFor(displayYear)}
          </div>
        </div>
        <button
          type="button"
          onClick={() => setGanttOpen((o) => !o)}
          aria-label={ganttOpen ? 'Close historical periods' : 'Open historical periods'}
          className="grid size-6 flex-none place-items-center rounded-md border bg-card text-muted-foreground hover:bg-muted md:mt-1 md:self-start"
        >
          {ganttOpen ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
        </button>
      </div>

      <div
        className="relative min-w-0 flex-1"
        style={{ height: BAR_PX }}
        onPointerDownCapture={() => {
          scrubbingRef.current = true;
        }}
      >
        <Timescope
          width="100%"
          height={`${BAR_PX}px`}
          time={committedYear}
          timeRange={TIME_RANGE}
          indicator
          onTimeChanging={(v) => {
            if (!scrubbingRef.current) return;
            const y = toYear(v);
            if (y !== null) setLiveScrub(clampYear(y));
          }}
          onTimeChanged={(v) => {
            if (!scrubbingRef.current) return;
            const y = toYear(v);
            if (y !== null) commit(clampYear(y));
          }}
          sources={EMPTY}
          series={EMPTY}
          tracks={TRACKS}
        />
      </div>
    </div>
  );
}
