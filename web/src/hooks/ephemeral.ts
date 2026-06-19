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

/** Bottom-timeline expanded/collapsed state (gantt vs scrubber). */
export function useTimelineExpanded() {
  const expanded = useEphemeralStore((s) => s.timelineExpanded);
  const setExpanded = useEphemeralStore((s) => s.setTimelineExpanded);
  const toggle = useCallback(() => setExpanded(!expanded), [expanded, setExpanded]);
  return { expanded, setExpanded, toggle };
}
