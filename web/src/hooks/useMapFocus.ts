import type { PaddingOptions } from 'maplibre-gl';
import { useCallback } from 'react';
import { geometriesBounds, isPointBounds } from '@/lib/map-focus';
import type { FocusBounds } from '@/lib/map-focus';
import { useMapInstance } from './ephemeral';
import { useIsMobile } from './useMediaQuery';

/** Zoom used when focusing a single point (no area to fit). */
const POINT_ZOOM = 5.5;
/** Never zoom past this when fitting an area — keeps some context around it. */
const MAX_FIT_ZOOM = 7;
const FLY_DURATION_MS = 900;

/**
 * Padding (px) that keeps the framed content clear of the floating panels: the
 * left sidebar (≤340) + right detail/tour panel (380) on desktop, the bottom
 * sheet on mobile (which can cover up to half the viewport).
 */
function focusPadding(isMobile: boolean): PaddingOptions {
  const w = typeof window !== 'undefined' ? window.innerWidth : 1280;
  const h = typeof window !== 'undefined' ? window.innerHeight : 800;
  if (isMobile) {
    // The sheet can cover up to half the viewport; keep the sides slim.
    return { top: 56, right: 28, bottom: Math.min(Math.round(h * 0.5), 380), left: 28 };
  }
  // Clear the left sidebar (≤340) + right detail/tour panel (380), but never pad
  // past the canvas on a narrow window (fitBounds misbehaves otherwise).
  return {
    top: 76,
    bottom: 96,
    left: Math.min(360, Math.round(w * 0.35)),
    right: Math.min(400, Math.round(w * 0.4)),
  };
}

/**
 * Imperative "focus the map on this geometry" handle. Frames a single entity or
 * a whole set (a chronicle step's cast) and animates there. A single point
 * flies to a sensible zoom; an area is fit with a max-zoom so a tiny territory
 * doesn't slam to street level. No-op until the map instance is ready.
 */
export function useMapFocus() {
  const { map } = useMapInstance();
  const isMobile = useIsMobile();

  const focusBounds = useCallback(
    (bounds: FocusBounds | null) => {
      if (!map || !bounds) return;
      const padding = focusPadding(isMobile);
      if (isPointBounds(bounds)) {
        map.flyTo({
          center: bounds[0],
          zoom: Math.max(map.getZoom(), POINT_ZOOM),
          padding,
          duration: FLY_DURATION_MS,
        });
      } else {
        map.fitBounds(bounds, {
          padding,
          maxZoom: MAX_FIT_ZOOM,
          duration: FLY_DURATION_MS,
        });
      }
    },
    [map, isMobile],
  );

  const focusGeometries = useCallback(
    (geoms: unknown[]) => focusBounds(geometriesBounds(geoms)),
    [focusBounds],
  );

  return { focusBounds, focusGeometries };
}
