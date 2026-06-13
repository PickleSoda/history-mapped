import { useMemo } from 'react';
import { snapScope } from '@/lib/scope/snap';
import type { Scope } from '@/types/atlas';
import { useFilters } from './useFilters';
import { useTimeState } from './useTimeState';
import { useViewport } from './useViewport';

/**
 * The query input (spec §3). Reads viewport + time + filters and returns the
 * snapped {bbox, z, time, groups}. Memoized on a serialized key so the object
 * is referentially stable — query keys don't thrash when React re-renders for
 * an unrelated reason.
 */
export function useScope(): Scope {
  const { bbox } = useViewport();
  const { time } = useTimeState();
  const { groups } = useFilters();

  const key = JSON.stringify({ bbox, time, groups });

  // eslint-disable-next-line react-hooks/exhaustive-deps
  return useMemo(() => snapScope({ bbox, time, groups }), [key]);
}
