import { useQueryState } from 'nuqs';
import { useCallback } from 'react';
import { parseAsTime } from '@/lib/url/params';
import type { TimeState } from '@/types/atlas';

const DEFAULT_TIME: TimeState = { kind: 'instant', year: 1121 };

/**
 * Timeline position <-> URL `t` (instant or range). Written with `replace`
 * (continuous). The scrubber commits here on release; playback steps the year.
 */
export function useTimeState() {
  const [time, setTime] = useQueryState(
    't',
    parseAsTime.withDefault(DEFAULT_TIME).withOptions({ history: 'replace' }),
  );

  const setInstant = useCallback(
    (year: number) => setTime({ kind: 'instant', year }),
    [setTime],
  );

  const setRange = useCallback(
    (start: number, end: number) => setTime({ kind: 'range', start, end }),
    [setTime],
  );

  /** Step the instant by `delta` years (used by playback). No-op on a range. */
  const step = useCallback(
    (delta: number) =>
      setTime((prev) =>
        prev?.kind === 'instant'
          ? { kind: 'instant', year: prev.year + delta }
          : prev,
      ),
    [setTime],
  );

  return { time, setTime, setInstant, setRange, step };
}
