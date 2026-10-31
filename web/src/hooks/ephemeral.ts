/**
 * Ephemeral/imperative hooks — slice-level selectors over the zustand store
 * (spec §5). Each reads exactly the slice it needs so a hover change can't
 * re-render a component that only cares about the sheet height.
 */
import { useCallback } from 'react';
import { useEphemeralStore } from '@/stores/ephemeral';
import { useTimeState } from './useTimeState';

/** Imperative handle to the maplibre map (flyTo, setFeatureState). */
export function useMapInstance() {
  const map = useEphemeralStore((s) => s.map);
  const setMap = useEphemeralStore((s) => s.setMap);
  return { map, setMap };
}

/** Changes whenever the map's style has been (re)built with our overlay in. */
export function useStyleEpoch() {
  const styleEpoch = useEphemeralStore((s) => s.styleEpoch);
  const bumpStyleEpoch = useEphemeralStore((s) => s.bumpStyleEpoch);
  return { styleEpoch, bumpStyleEpoch };
}

/**
 * Uncommitted scrub value during a drag. Drives the readout/ghost filter at
 * 60fps; `commit` writes the final year to the URL on release.
 */
export function useLiveScrub() {
  const liveScrub = useEphemeralStore((s) => s.liveScrub);
  const setLiveScrub = useEphemeralStore((s) => s.setLiveScrub);
  const { setInstant } = useTimeState();

  const commit = useCallback(
    (year: number) => {
      setInstant(year);
      setLiveScrub(null);
    },
    [setInstant, setLiveScrub],
  );

  return { liveScrub, setLiveScrub, commit };
}

/** Hovered entity id for list <-> map cross-highlight. */
export function useHover() {
  const hoverId = useEphemeralStore((s) => s.hoverId);
  const setHover = useEphemeralStore((s) => s.setHover);
  return { hoverId, setHover };
}

/** True once the shell has measured what covers the map. Viewport queries
 *  wait for it so they don't first fetch the area under the panels. */
export function useMapInsetsReady() {
  return useEphemeralStore((s) => s.mapInsets != null);
}

/** Mobile bottom-sheet height (peek / half / full). */
export function useSheet() {
  const sheet = useEphemeralStore((s) => s.sheet);
  const setSheet = useEphemeralStore((s) => s.setSheet);
  return { sheet, setSheet };
}

/** Command palette open state + helpers. (⌘K binding lives in the component.) */
export function useCommandPalette() {
  const open = useEphemeralStore((s) => s.paletteOpen);
  const setPaletteOpen = useEphemeralStore((s) => s.setPaletteOpen);
  const toggle = useCallback(
    () => setPaletteOpen(!open),
    [open, setPaletteOpen],
  );
  return { open, setOpen: setPaletteOpen, toggle };
}
