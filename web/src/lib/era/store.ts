import { create } from 'zustand';
import type { EraEntry, EraTheme } from '@/lib/era/types';

/**
 * Era-theme state shared by the document styling (useEraTheme), the map
 * (EraLayer) and the UI that names the era. `enabled` is a per-viewer
 * preference kept in localStorage; everything else follows the map.
 */
const STORAGE_KEY = 'hm-era-style';

function storedEnabled(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) !== 'off';
  } catch {
    return true;
  }
}

interface EraState {
  enabled: boolean;
  /** The applied era and its loaded theme; null while off or loading. */
  entry: EraEntry | null;
  theme: EraTheme | null;
  setEnabled: (enabled: boolean) => void;
  setActive: (entry: EraEntry | null, theme: EraTheme | null) => void;
}

export const useEra = create<EraState>((set) => ({
  enabled: storedEnabled(),
  entry: null,
  theme: null,
  setEnabled: (enabled) => {
    try {
      localStorage.setItem(STORAGE_KEY, enabled ? 'on' : 'off');
    } catch {
      /* private mode: the choice lasts for this page */
    }
    set({ enabled });
  },
  setActive: (entry, theme) => set({ entry, theme }),
}));
