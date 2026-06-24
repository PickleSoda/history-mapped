import { useQueryStates } from 'nuqs';
import { useCallback, useEffect, useMemo } from 'react';
import { focusOf, reconcileTrail } from '@/lib/nav-trail';
import type { Crumb } from '@/lib/nav-trail';
import { parseAsChronicle, parseAsSelection, parseAsStep } from '@/lib/url/params';
import { useEphemeralStore } from '@/stores/ephemeral';
import { useChronicle } from './useChronicle';
import { useEntity } from './useEntity';

/** The nav-state keys the trail is derived from / restores. */
const NAV_KEYS = {
  sel: parseAsSelection,
  chron: parseAsChronicle,
  step: parseAsStep.withDefault(0),
};

/**
 * Keeps the breadcrumb trail in step with the nav state and the browser back
 * button. Call this ONCE at the shell root so the trail builds regardless of
 * where the breadcrumb is rendered (or whether it is rendered at all).
 */
export function useNavTrailSync(): void {
  const [{ sel, chron, step }] = useQueryStates(NAV_KEYS, { history: 'push' });
  const setTrail = useEphemeralStore((s) => s.setTrail);

  // Names for the current focus (cached — these queries already back the panels).
  const { data: entityData } = useEntity(sel);
  const { data: chronData } = useChronicle(chron);

  const next = useMemo(
    () =>
      focusOf(
        { sel, chron, step },
        {
          entityLabel: entityData?.name,
          entityGroup: entityData?.entity_group,
          chronicleLabel: chronData?.title,
        },
      ),
    [sel, chron, step, entityData?.name, entityData?.entity_group, chronData?.title],
  );

  useEffect(() => {
    setTrail((prev) => reconcileTrail(prev, next));
  }, [next, setTrail]);
}

/** The trail + a jump-to-crumb action, for rendering the breadcrumb. */
export function useNavTrail(): { trail: Crumb[]; goTo: (index: number) => void } {
  const [, setNav] = useQueryStates(NAV_KEYS, { history: 'push' });
  const trail = useEphemeralStore((s) => s.trail);
  const setTrail = useEphemeralStore((s) => s.setTrail);

  const goTo = useCallback(
    (index: number) => {
      const crumb = useEphemeralStore.getState().trail[index];
      if (!crumb) return;
      void setNav({ sel: crumb.sel, chron: crumb.chron, step: crumb.step });
      setTrail((prev) => prev.slice(0, index + 1));
    },
    [setNav, setTrail],
  );

  return { trail, goTo };
}
