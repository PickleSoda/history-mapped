import { useQueryState } from 'nuqs';
import { useCallback } from 'react';
import { parseAsBbox } from '@/lib/url/params';
import type { Bbox } from '@/types/atlas';

/** Initial world-ish view used when the URL has no bbox. */
const DEFAULT_BBOX: Bbox = { w: -25, s: 30, e: 65, n: 70 };

/**
 * Raw map viewport <-> URL `bbox`. Written with `replace` (one history entry
 * per gesture, not per frame). The map commits the bbox on move-end; this hook
 * just owns the read/write seam.
 */
export function useViewport() {
  const [bbox, setBbox] = useQueryState(
    'bbox',
    parseAsBbox.withDefault(DEFAULT_BBOX).withOptions({ history: 'replace' }),
  );

  const commit = useCallback((next: Bbox) => setBbox(next), [setBbox]);

  return { bbox, setBbox: commit };
}
