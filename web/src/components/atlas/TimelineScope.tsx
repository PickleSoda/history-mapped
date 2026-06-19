import { Timescope } from '@timescope/react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { useLiveScrub, useTimeState, useTimelineExpanded } from '@/hooks';
import { eraFor, formatYear, instantYear } from '@/lib/format';
import { groupColor } from '@/lib/timeline/colors';
import { sampleSpans, SAMPLE_LANES } from '@/lib/timeline/sampleSpans';
import { toYear } from '@/lib/timeline/year';
import { cn } from '@/lib/utils';

const TRACK = 'main';

/**
 * Bottom timeline (design: 2026-06-19-bottom-timeline-timescope). Renders a
 * sample entity-lifespan gantt over a plain historical-year domain, with the
 * playhead reflecting the current year. Playhead is wired to live scrub +
 * commit; collapsible between a scrubber and the gantt.
 */
export function TimelineScope() {
  const { time } = useTimeState();
  const { liveScrub, setLiveScrub, commit } = useLiveScrub();
  const committedYear = instantYear(time);
  const displayYear = liveScrub ?? committedYear;
  const { expanded, toggle } = useTimelineExpanded();
  const trackHeight = expanded ? 150 : 28;

  return (
    <div className={cn('flex items-stretch transition-[height]', expanded ? 'h-[170px]' : 'h-14')}>
      <div className="flex w-[150px] flex-none flex-col justify-center px-4 leading-tight">
        <span className="font-mono text-sm tabular-nums">{formatYear(displayYear)}</span>
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {eraFor(displayYear)}
        </span>
        <button
          type="button"
          onClick={toggle}
          aria-label={expanded ? 'Collapse timeline' : 'Expand timeline'}
          className="mt-1 grid size-6 place-items-center self-start rounded-md border bg-card text-muted-foreground hover:bg-muted"
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
        </button>
      </div>

      <div className="relative min-w-0 flex-1">
        <Timescope
          width="100%"
          height="100%"
          time={committedYear}
          indicator
          onTimeChanging={(v) => {
            const y = toYear(v);
            if (y !== null) setLiveScrub(y);
          }}
          onTimeChanged={(v) => {
            const y = toYear(v);
            if (y !== null) commit(y);
          }}
          sources={{ spans: sampleSpans }}
          series={
            expanded
              ? {
                  spans: {
                    data: {
                      source: 'spans',
                      time: { start: 'start', end: 'end' },
                      value: { lane: 'lane' },
                      range: [0, SAMPLE_LANES],
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
                            fillColor: ({ data }) => groupColor(data.group),
                            fillOpacity: 0.85,
                            lineWidth: 1.5,
                            lineColor: ({ data }) => groupColor(data.group),
                          },
                        },
                        {
                          draw: 'text',
                          using: 'lane@start',
                          style: {
                            size: 12,
                            text: ({ data }) => data.label,
                            textAlign: 'start',
                            textColor: '#1f2937',
                            textOutline: true,
                            textOutlineColor: '#ffffff',
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
                // .number() converts the @kikuchan/decimal tick value to a float;
              // round to a whole year for the BCE/CE axis label.
              timeFormat: (opts) => formatYear(Math.round(opts.time.number())),
              },
            },
          }}
        />
      </div>
    </div>
  );
}
