import { useQueryState } from 'nuqs';
import { useCallback, useMemo } from 'react';
import { parseAsGroups } from '@/lib/url/params';
import { ENTITY_GROUPS  } from '@/types/atlas';
import type {EntityGroup} from '@/types/atlas';

/**
 * Active group filters <-> URL `g`. Filters shape both the list and the map, so
 * they are part of scope and live in the URL. An empty/absent param means "all
 * groups". Written with `replace` (a refinement, not a destination).
 */
export function useFilters() {
  const [raw, setRaw] = useQueryState(
    'g',
    parseAsGroups.withDefault([]).withOptions({ history: 'replace' }),
  );

  // Empty selection means "all" — expose the resolved active set.
  const groups = useMemo<EntityGroup[]>(
    () => (raw.length ? raw : [...ENTITY_GROUPS]),
    [raw],
  );

  const toggle = useCallback(
    (group: EntityGroup) =>
      setRaw((prev) => {
        const current = prev ?? [];
        const next = current.includes(group)
          ? current.filter((g) => g !== group)
          : [...current, group];
        // Collapse "all selected" back to the empty (= all) representation.
        return next.length === ENTITY_GROUPS.length ? [] : next;
      }),
    [setRaw],
  );

  const isActive = useCallback(
    (group: EntityGroup) => groups.includes(group),
    [groups],
  );

  const clear = useCallback(() => setRaw([]), [setRaw]);

  return { groups, raw, toggle, isActive, clear };
}
