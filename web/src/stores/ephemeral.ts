/**
 * Ephemeral state (spec §1, Ephemeral layer).
 *
 * Interaction-only values that are intentionally lost on refresh: the live
 * (uncommitted) scrub value, hover target, command-palette open state, mobile
 * sheet height, and the imperative map instance ref. Read with SELECTORS
 * (`useEphemeralStore(s => s.hoverId)`) — never subscribe to the whole store.
 */
import type { Map as MaplibreMap } from 'maplibre-gl';
import { create } from 'zustand';

export type SheetHeight = 'peek' | 'half' | 'full';

interface EphemeralState {
  /** Uncommitted scrub year during a drag; null when not scrubbing. */
  liveScrub: number | null;
  /** Hovered entity id for list <-> map cross-highlight. */
  hoverId: string | null;
  /** Command palette (⌘K) open state. */
  paletteOpen: boolean;
  /** Mobile bottom-sheet height. */
  sheet: SheetHeight;
  /** Imperative handle to the maplibre map. Not React state for renders. */
  map: MaplibreMap | null;

  setLiveScrub: (year: number | null) => void;
  setHover: (id: string | null) => void;
  setPaletteOpen: (open: boolean) => void;
  setSheet: (height: SheetHeight) => void;
  setMap: (map: MaplibreMap | null) => void;
}

export const useEphemeralStore = create<EphemeralState>()((set) => ({
  liveScrub: null,
  hoverId: null,
  paletteOpen: false,
  sheet: 'peek',
  map: null,

  setLiveScrub: (liveScrub) => set({ liveScrub }),
  setHover: (hoverId) => set({ hoverId }),
  setPaletteOpen: (paletteOpen) => set({ paletteOpen }),
  setSheet: (sheet) => set({ sheet }),
  setMap: (map) => set({ map }),
}));
