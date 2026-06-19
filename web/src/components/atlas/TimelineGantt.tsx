import { Timescope } from '@timescope/react';
import { useMemo } from 'react';
import { useHistoricalPeriods, useTimeState } from '@/hooks';
import { formatYear, instantYear } from '@/lib/format';
import { laneCount, periodsToSpans } from '@/lib/timeline/periods';
import { APP_FONT_FAMILY, labelOutlineColor, labelTextColor } from '@/lib/timeline/theme';
import { AXIS_MAX, AXIS_MIN } from '@/lib/timeline/year';

const TRACK = 'main';
const TIME_RANGE: [number, number] = [AXIS_MIN, AXIS_MAX];
const PANEL_PX = 220;

/**
 * The historical-periods gantt, shown in a panel opened from the timeline bar.
 *
 * It is READ-ONLY: it renders the current year as an indicator but has no
 * `onTimeChanged`/`onTimeChanging`, so timescope's animation can never feed back
 * into the URL time state (that feedback is what caused the scrub flicker). All
 * timescope option objects are memoised so a time change doesn't reload the data.
 */
export function TimelineGantt() {
  const { time } = useTimeState();
  const { data: periods } = useHistoricalPeriods();
  const year = instantYear(time);

  const spans = useMemo(() => periodsToSpans(periods ?? []), [periods]);
  const lanes = useMemo(() => laneCount(spans), [spans]);
  const textColor = labelTextColor();
  const outlineColor = labelOutlineColor();

  const sources = useMemo(() => ({ spans }), [spans]);

  const series = useMemo(
    () => ({
      spans: {
        data: {
          source: 'spans',
          time: { start: 'start', end: 'end' },
          value: { lane: 'lane' },
          // Lock the value range (timescope auto-expands to fit data otherwise)
          // and reserve footroom so the bottom lane clears the date axis.
          range: {
            default: [-0.5, lanes + 1.2],
            expand: false,
            shrink: false,
          } as { default: [number, number]; expand: boolean; shrink: boolean },
        },
        track: TRACK,
        chart: {
          marks: [
            {
              draw: 'box' as const,
              using: ['lane@start', 'lane@end'],
              style: {
                size: 18,
                radius: 3,
                fillColor: ({ data }: { data: Record<string, unknown> }) => data.color as string,
                fillOpacity: 0.85,
                lineWidth: 1.5,
                lineColor: ({ data }: { data: Record<string, unknown> }) => data.color as string,
              },
            },
            {
              draw: 'text' as const,
              using: 'lane@start',
              style: {
                size: 12,
                fontFamily: APP_FONT_FAMILY,
                text: ({ data }: { data: Record<string, unknown> }) => data.label as string,
                textAlign: 'start',
                textColor,
                textOutline: true,
                textOutlineColor: outlineColor,
                textOutlineWidth: 3,
                offset: ({ data }: { data: Record<string, number> }) => [
                  (data.end - data.start) * 0.5,
                  0,
                ],
              },
            },
          ],
        },
      },
    }),
    [lanes, textColor, outlineColor],
  );

  const tracks = useMemo(
    () => ({
      [TRACK]: {
        timeAxis: {
          labels: { fontFamily: APP_FONT_FAMILY },
          timeFormat: (opts: { time: { number(): number } }) =>
            formatYear(Math.round(opts.time.number())),
        },
      },
    }),
    [],
  );

  return (
    <div className="relative w-full" style={{ height: PANEL_PX }}>
      <Timescope
        width="100%"
        height={`${PANEL_PX}px`}
        time={year}
        timeRange={TIME_RANGE}
        indicator
        sources={sources}
        series={series}
        tracks={tracks}
      />
    </div>
  );
}
