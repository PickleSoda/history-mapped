import { Timescope } from '@timescope/react';
import { useEffect, useMemo, useRef } from 'react';
import { useLiveScrub, useTimeState } from '@/hooks';
import { eraFor, formatYear, instantYear } from '@/lib/format';
import {
  APP_FONT_FAMILY,
  axisLabelColor,
  axisLineColor,
} from '@/lib/timeline/theme';
import { AXIS_MAX, AXIS_MIN, clampYear, toYear } from '@/lib/timeline/year';

const TRACK = 'main';
const BAR_PX = 30;

/** Stable identities so the @timescope/react effects don't re-fire each render. */
const TIME_RANGE: [number, number] = [AXIS_MIN, AXIS_MAX];
const EMPTY = {};

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
  const scrubbingRef = useRef(false);
  // Latest year seen during the active drag; committed to global time on release.
  const pendingYearRef = useRef<number | null>(null);
  // commit() is recreated when its deps change; keep a live ref for the
  // once-registered window listener below.
  const commitRef = useRef(commit);
  useEffect(() => {
    commitRef.current = commit;
  }, [commit]);

  useEffect(() => {
    // Commit the dragged year to global time on pointer release. We commit here
    // (not in timescope's async `timechanged`, whose timing relative to pointerup
    // is unreliable) so a real drag always updates the global year, while
    // programmatic setTime (chronicle/TopBar) — where no pointer is down — is
    // ignored because `scrubbingRef` stays false.
    const end = () => {
      if (!scrubbingRef.current) return;
      scrubbingRef.current = false;
      const y = pendingYearRef.current;
      pendingYearRef.current = null;
      if (y !== null) commitRef.current(y);
    };
    window.addEventListener('pointerup', end);
    window.addEventListener('pointercancel', end);
    return () => {
      window.removeEventListener('pointerup', end);
      window.removeEventListener('pointercancel', end);
    };
  }, []);

  // Canvas-themed axis: muted line/ticks, muted-foreground Geist labels.
  // Memoised so @timescope/react effects keep a stable identity (colours read
  // once at mount; they reflect the active light/dark theme).
  const tracks = useMemo(
    () => ({
      [TRACK]: {
        timeAxis: {
          axis: { color: axisLineColor() },
          ticks: { color: axisLineColor() },
          labels: {
            fontFamily: APP_FONT_FAMILY,
            fontSize: '11px',
            color: axisLabelColor(),
          },
          timeFormat: (opts: { time: { number(): number } }) =>
            formatYear(Math.round(opts.time.number())),
        },
      },
    }),
    [],
  );

  return (
    <div className="relative flex flex-col-reverse md:flex-row h20 px-2 md:px-10 py-2 ">
      {/* Readout + open/close button — left column on desktop, bottom row on mobile. */}
      <div className="leading-tight flex flex-none flex-row items-end justify-start gap-2 px-2 py-0.5 md:w-[150px] md:flex-col md:items-start md:justify-center md:py-0" >
        <div className="font-mono text-sm tabular-nums">{formatYear(displayYear)}</div>
        <div className="text-[10px] uppercase tracking-wide text-muted-foreground ">
          {eraFor(displayYear)}
        </div>

      </div>

      <div
        className="relative min-w-0 flex-1 rounded-lg border border-border bg-muted/50 px-2 py-0.5"
        style={{ height: BAR_PX + 10 }}
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
            if (y !== null) {
              const cy = clampYear(y);
              pendingYearRef.current = cy;
              setLiveScrub(cy);
            }
          }}
          onTimeChanged={(v) => {
            if (!scrubbingRef.current) return;
            const y = toYear(v);
            if (y !== null) {
              const cy = clampYear(y);
              pendingYearRef.current = cy;
              setLiveScrub(cy);
            }
          }}
          sources={EMPTY}
          series={EMPTY}
          tracks={tracks}
        />
      </div>
    </div>
  );
}
