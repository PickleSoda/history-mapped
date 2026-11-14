import { useEffect, useMemo } from 'react';
import { activateEraTheme, deactivateEraTheme, refreshEraThemeColor } from '@/lib/era/apply';
import { loadEraTheme } from '@/lib/era/loader';
import { resolveEra } from '@/lib/era/resolve';
import { useEra } from '@/lib/era/store';
import type { EraEntry } from '@/lib/era/types';
import { instantYear } from '@/lib/format';
import { cropBbox } from '@/lib/scope/snap';
import { useTheme } from '@/lib/theme';
import { useEphemeralStore } from '@/stores/ephemeral';
import type { Bbox } from '@/types/atlas';
import { useTimeState } from './useTimeState';
import { useViewport } from './useViewport';

/** Wait this long after the view or year settles before restyling. */
const SETTLE_MS = 300;

/** The part of the map the panels leave visible. */
export function useVisibleBbox(): Bbox {
  const { bbox } = useViewport();
  const insets = useEphemeralStore((s) => s.mapInsets);
  return useMemo(() => (insets ? cropBbox(bbox, insets) : bbox), [bbox, insets]);
}

/** The era for `year` (default: the timeline's) and the visible map. */
export function useEraEntry(year?: number): EraEntry {
  const { time } = useTimeState();
  const visible = useVisibleBbox();
  const y = year ?? instantYear(time);
  return useMemo(() => resolveEra(y, visible), [y, visible]);
}

/**
 * Restyles the atlas for the era on the map: resolves it from the committed
 * year and the visible map, loads that era's theme module (its first use
 * fetches the chunk) and applies it to the document. Mount once, in the atlas
 * layout; leaving the atlas puts the default look back.
 */
export function useEraTheme(): void {
  const entry = useEraEntry();
  const enabled = useEra((s) => s.enabled);
  const setActive = useEra((s) => s.setActive);
  const mode = useTheme((s) => s.theme);

  useEffect(() => {
    if (!enabled) {
      deactivateEraTheme();
      setActive(null, null);
      return;
    }
    let stale = false;
    const timer = setTimeout(() => {
      loadEraTheme(entry.theme).then(
        (theme) => {
          if (stale) return;
          activateEraTheme(theme);
          setActive(entry, theme);
        },
        (error: unknown) => console.warn('[era] theme failed to load', entry.theme, error),
      );
    }, SETTLE_MS);
    return () => {
      stale = true;
      clearTimeout(timer);
    };
  }, [entry, enabled, setActive]);

  // The browser chrome colour follows light/dark mode too.
  useEffect(() => {
    refreshEraThemeColor(useEra.getState().theme);
  }, [mode]);

  useEffect(
    () => () => {
      deactivateEraTheme();
      useEra.getState().setActive(null, null);
    },
    [],
  );
}
