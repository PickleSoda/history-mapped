import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { ambientStories } from '@/lib/api/map-stories';
import { snapAmbientBbox } from '@/lib/map-story/steps';
import type { Bbox } from '@/types/atlas';

/** Wait for the timeline and the viewport to settle before asking. */
const DEBOUNCE_MS = 300;

/**
 * The ambient stories at `year` in the viewport (GET /map-stories/ambient):
 * what the plain atlas draws faintly when no story or chronicle plays.
 * Debounced, and keyed on the year and the viewport snapped to a tile grid,
 * so scrubbing and small pans reuse the cache; the previous answer stays on
 * screen while the next loads.
 */
export function useAmbientStories(year: number, bbox: Bbox, enabled = true) {
  const target = JSON.stringify([Math.round(year), ...snapAmbientBbox(bbox)]);
  const [key, setKey] = useState(target);
  useEffect(() => {
    if (target === key) return;
    const timer = setTimeout(() => setKey(target), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [target, key]);

  return useQuery({
    // Not in `qk`, which this part doesn't own: the one key for this endpoint.
    queryKey: ['map-stories', 'ambient', key],
    queryFn: ({ signal }) => {
      const [y, w, s, e, n] = JSON.parse(key) as number[];
      return ambientStories(y, [w, s, e, n], signal);
    },
    enabled,
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
  });
}
