import { Timescope } from '@timescope/react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { useEffect, useMemo, useRef } from 'react';
import { useHistoricalPeriods, useLiveScrub, useTimeState, useTimelineMode } from '@/hooks';
import { eraFor, formatYear, instantYear } from '@/lib/format';
import { laneCount, periodsToSpans } from '@/lib/timeline/periods';
import { APP_FONT_FAMILY, labelOutlineColor, labelTextColor } from '@/lib/timeline/theme';
import { AXIS_MAX, AXIS_MIN, clampYear, toYear } from '@/lib/timeline/year';
import { cn } from '@/lib/utils';

const TRACK = 'main';

/**
 * Bottom timeline. Collapsed it is a thin, read-only scrubber; clicking it
 * transiently expands the historical-periods gantt and enables dragging the
 * playhead, then auto-closes on pointer-leave / tap-outside. The chevron pins
 * it open. Time is clamped to {@link AXIS_MIN}..{@link AXIS_MAX}.
 */
export function TimelineScope() {
  const { time } = useTimeState();
  const { liveScrub, setLiveScrub, commit } = useLiveScrub();
  const { mode, expanded, expandTransient, collapse, togglePin } = useTimelineMode();
  const { data: periods } = useHistoricalPeriods();

  const committedYear = instantYear(time);
  const displayYear = liveScrub ?? committedYear;

  const spans = useMemo(() => periodsToSpans(periods ?? []), [periods]);
  const lanes = useMemo(() => laneCount(spans), [spans]);
  const showGantt = expanded && spans.length > 0;
  const trackHeight = expanded ? 150 : 28;

  const containerRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);

  // Auto-close a transiently-opened timeline on tap/click outside (covers
  // touch, where pointer-leave never fires). Pinned mode ignores this.
  useEffect(() => {
    if (mode !== 'transient') return;
    const onPointerDown = (e: PointerEvent) => {
      if (draggingRef.current) return;
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        collapse();
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [mode, collapse]);

  return (
    <div
      ref={containerRef}
      onMouseLeave={() => {
        if (mode === 'transient' && !draggingRef.current) collapse();
      }}
      className={cn(
        'flex flex-col-reverse overflow-hidden transition-[height] md:flex-row',
        expanded ? 'h-[170px]' : 'h-14',
      )}
    >
      {/* Readout + opener — left column on desktop, bottom row on small screens. */}
      <div className="flex flex-none flex-row items-center justify-between gap-2 px-4 py-1 md:w-[150px] md:flex-col md:items-start md:justify-center md:py-0">
        <div className="leading-tight">
          <div className="font-mono text-sm tabular-nums">{formatYear(displayYear)}</div>
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
            {eraFor(displayYear)}
          </div>
        </div>
        <button
          type="button"
          onClick={togglePin}
          aria-label={expanded ? 'Collapse timeline' : 'Pin timeline open'}
          className="grid size-6 flex-none place-items-center rounded-md border bg-card text-muted-foreground hover:bg-muted md:mt-1 md:self-start"
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
        </button>
      </div>

      <div className="relative min-w-0 flex-1">
        <Timescope
          width="100%"
          height="100%"
          time={committedYear}
          timeRange={[AXIS_MIN, AXIS_MAX]}
          indicator
          onTimeChanging={(v) => {
            draggingRef.current = true;
            const y = toYear(v);
            if (y !== null) setLiveScrub(clampYear(y));
          }}
          onTimeChanged={(v) => {
            draggingRef.current = false;
            const y = toYear(v);
            if (y !== null) commit(clampYear(y));
          }}
          sources={{ spans }}
          series={
            showGantt
              ? {
                  spans: {
                    data: {
                      source: 'spans',
                      time: { start: 'start', end: 'end' },
                      value: { lane: 'lane' },
                      range: [0, lanes],
                    },
                    track: TRACK,
                    chart: {
                      marks: [
                        {
                          draw: 'box',
                          using: ['lane@start', 'lane@end'],
                          style: {
                            size: 16,
                            radius: 3,
                            fillColor: ({ data }) => data.color,
                            fillOpacity: 0.85,
                            lineWidth: 1.5,
                            lineColor: ({ data }) => data.color,
                          },
                        },
                        {
                          draw: 'text',
                          using: 'lane@start',
                          style: {
                            size: 12,
                            fontFamily: APP_FONT_FAMILY,
                            text: ({ data }) => data.label,
                            textAlign: 'start',
                            textColor: labelTextColor(),
                            textOutline: true,
                            textOutlineColor: labelOutlineColor(),
                            textOutlineWidth: 3,
                            offset: ({ data }) => [(data.end - data.start) * 0.5, 0],
                          },
                        },
                      ],
                    },
                  },
                }
              : {}
          }
          tracks={{
            [TRACK]: {
              height: trackHeight,
              timeAxis: {
                labels: { fontFamily: APP_FONT_FAMILY },
                // .number() converts the @kikuchan/decimal tick value to a float;
                // round to a whole year for the BCE/CE axis label.
                timeFormat: (opts) => formatYear(Math.round(opts.time.number())),
              },
            },
          }}
        />

        {/* When collapsed, intercept clicks so the canvas can't be scrubbed;
            the first click just expands (transient). */}
        {!expanded && (
          <button
            type="button"
            aria-label="Expand timeline"
            onClick={expandTransient}
            className="absolute inset-0 z-10 cursor-pointer"
          />
        )}
      </div>
    </div>
  );
}
