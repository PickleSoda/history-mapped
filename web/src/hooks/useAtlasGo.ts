import { useQueryStates } from 'nuqs';
import { useCallback } from 'react';
import { pointsBounds } from '@/lib/map-focus';
import { parseAsSelection, parseAsTime } from '@/lib/url/params';
import type { TimeState } from '@/types/atlas';
import { useMapFocus } from './useMapFocus';

/** Where to take the atlas: a year, an entity to open, a point to fly to. */
export interface AtlasGoTarget {
  /** Open this entity (its panel then frames it on the map). */
  id?: string | null;
  /** Put the timeline at this year (BCE negative). */
  year?: number | null;
  /** Fly here, [lng, lat]. Used when no entity is opened. */
  at?: [number, number] | null;
}

/**
 * "Go there" from inside the atlas: the timeline year and the selection in one
 * URL write (one Back step), and a camera move when only a place is given.
 * Only for components mounted in the atlas (`/app`): on a site page it would
 * rewrite that page's URL, so link with `atlasHref` there instead.
 */
export function useAtlasGo() {
  const [, set] = useQueryStates({ t: parseAsTime, sel: parseAsSelection }, { history: 'push' });
  const { focusBounds } = useMapFocus();

  return useCallback(
    ({ id, year, at }: AtlasGoTarget) => {
      const patch: { t?: TimeState; sel?: string } = {};
      if (year != null && Number.isFinite(year)) patch.t = { kind: 'instant', year: Math.trunc(year) };
      if (id) patch.sel = id;
      if (patch.t || patch.sel) void set(patch);
      if (!id && at) focusBounds(pointsBounds([at], 0));
    },
    [set, focusBounds],
  );
}
