import { Timescope } from '@timescope/react';
import { useEffect, useMemo, useRef } from 'react';
import { useEraEntry, useLiveScrub, useTimeState } from '@/hooks';
import { useEra } from '@/lib/era/store';
import { eraTokens } from '@/lib/era/tokens';
import { formatYear, instantYear } from '@/lib/format';
import { useTheme } from '@/lib/theme';
import {
  APP_FONT_FAMILY,
  axisLabelColor,
  axisLineColor,
} from '@/lib/timeline/theme';
import { AXIS_MAX, AXIS_MIN, clampYear, toYear } from '@/lib/timeline/year';

const TRACK = 'main';
const BAR_PX = 30;
/** A press released within this many pixels is a click, not a drag (timescope's own tolerance). */
const CLICK_PX = 8;
/** How long after a click's release timescope's report of the clicked year is waited for. */
const CLICK_SETTLE_MS = 700;

/** Stable identities so the @timescope/react effects don't re-fire each render. */
const TIME_RANGE: [number, number] = [AXIS_MIN, AXIS_MAX];
const EMPTY = {};

/**
 * Bottom timeline — a simple timescope scrubber (date axis + draggable playhead).
 *
 * Flicker fix: timescope's *programmatic* setTime (from a chronicle step or the
 * TopBar) animates the playhead and emits `timechanged` with intermediate frame
 * values. Committing those back to the URL caused the time state to oscillate.
 * We therefore only honour the time callbacks while the user is actually
 * pointer-dragging the canvas (`scrubbingRef`); programmatic changes are ignored.
 */
export function TimelineScope() {
  const { time } = useTimeState();
  const theme = useTheme((s) => s.theme);
  const { liveScrub, setLiveScrub, commit } = useLiveScrub();
  const committedYear = instantYear(time);
  const displayYear = liveScrub ?? committedYear;
  // The era of the year under the playhead and the visible map (live while
  // scrubbing); its theme, once applied, also colours the axis.
  const era = useEraEntry(displayYear);
  const eraTheme = useEra((s) => s.theme);
  const scrubbingRef = useRef(false);
  // Latest year seen during the active drag; committed to global time on release.
  const pendingYearRef = useRef<number | null>(null);
  // Where the pointer went down, to tell a click from a drag on release.
  const downRef = useRef<{ x: number; y: number } | null>(null);
  // After a click: until when timescope's report of the clicked year is honoured.
  const clickUntilRef = useRef(0);
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
    //
    // A click (press and release in place) is the exception: timescope moves
    // the playhead to the clicked year and reports it only after the release,
    // so that one report is let through for a moment (`clickUntilRef`).
    const end = (event: PointerEvent) => {
      if (!scrubbingRef.current) return;
      scrubbingRef.current = false;
      const y = pendingYearRef.current;
      pendingYearRef.current = null;
      const down = downRef.current;
      downRef.current = null;
      const clicked =
        event.type === 'pointerup' &&
        down !== null &&
        Math.hypot(event.clientX - down.x, event.clientY - down.y) < CLICK_PX;
      clickUntilRef.current = clicked ? performance.now() + CLICK_SETTLE_MS : 0;
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
  // Memoised on the light/dark theme and the era theme so colours re-derive
  // when either changes. An era's colours come from its tokens, not the CSS
  // (which eases between eras and would be read mid-transition).
  const tracks = useMemo(() => {
    const tokens = eraTheme ? eraTokens(eraTheme, theme) : null;
    const line = tokens?.['--border'] ?? axisLineColor();
    return {
      [TRACK]: {
        timeAxis: {
          axis: { color: line },
          ticks: { color: line },
          labels: {
            fontFamily: APP_FONT_FAMILY,
            fontSize: '11px',
            color: tokens?.['--muted-foreground'] ?? axisLabelColor(),
          },
          timeFormat: (opts: { time: { number(): number } }) =>
            formatYear(Math.round(opts.time.number())),
        },
      },
    };
  }, [theme, eraTheme]);

  return (
    <div className="relative flex flex-col-reverse md:flex-row h20 px-2 md:px-10 py-2 ">
      {/* Readout + open/close button — left column on desktop, bottom row on mobile. */}
      <div className="leading-tight flex flex-none flex-row items-end justify-start gap-2 px-2 py-0.5 md:w-[150px] md:flex-col md:items-start md:justify-center md:py-0" >
        <div className="font-mono text-sm tabular-nums">{formatYear(displayYear)}</div>
        <div className="text-[10px] uppercase tracking-wide text-muted-foreground ">
          {era.label}
        </div>

      </div>

      <div
        className="relative min-w-0 flex-1 rounded-lg border border-border bg-muted/50 px-2 py-0.5"
        style={{ height: BAR_PX + 10 }}
        onPointerDownCapture={(event) => {
          scrubbingRef.current = true;
          downRef.current = { x: event.clientX, y: event.clientY };
          clickUntilRef.current = 0;
        }}
      >
        <Timescope
          // Remount on a light/dark or era change: the canvas reads `tracks` (axis colors)
          // only once at mount, so this forces a fresh paint with the new
          // theme's colors — don't simplify this away.
          key={`${theme}:${eraTheme?.id ?? 'default'}`}
          width="100%"
          height={`${BAR_PX}px`}
          time={committedYear}
          timeRange={TIME_RANGE}
          background="transparent"
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
            if (!scrubbingRef.current) {
              // The year of a click, reported after its release: commit it, once.
              if (performance.now() > clickUntilRef.current) return;
              clickUntilRef.current = 0;
              const clickedYear = toYear(v);
              if (clickedYear !== null) commit(clampYear(clickedYear));
              return;
            }
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
