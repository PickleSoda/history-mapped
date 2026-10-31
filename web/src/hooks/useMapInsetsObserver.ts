import { useLayoutEffect } from 'react';
import type { RefObject } from 'react';
import { snapCoverPx } from '@/lib/sheet';
import { useEphemeralStore } from '@/stores/ephemeral';
import type { MapInsets } from '@/types/atlas';

/** Panels animate their width; let a transition settle before re-scoping. */
const SETTLE_MS = 150;
/** Insets are rounded to this share so a pixel of jitter can't change the scope. */
const STEP = 0.02;

const quantize = (share: number) => Math.round(share / STEP) * STEP;

const NONE: MapInsets = { top: 0, right: 0, bottom: 0, left: 0 };

const sameInsets = (a: MapInsets, b: MapInsets | null) =>
  b != null &&
  a.top === b.top &&
  a.right === b.right &&
  a.bottom === b.bottom &&
  a.left === b.left;

interface Occluders {
  /** The element the map fills. */
  map: RefObject<HTMLElement | null>;
  /** Overlays pinned to the map's left / right / top edge. */
  left?: RefObject<HTMLElement | null>;
  right?: RefObject<HTMLElement | null>;
  top?: RefObject<HTMLElement | null>;
  /** Active snap of a bottom sheet pinned to the viewport bottom (vaul). */
  bottomSnap?: number | string;
}

/**
 * Measures how much of the map the shell's floating UI covers and publishes it
 * as `mapInsets`, so the viewport queries skip what nobody can see. The first
 * measurement (and a sheet snap) publishes at once — the queries wait for it,
 * so a page load doesn't fetch the uncropped view first; resizes are debounced.
 */
export function useMapInsetsObserver({ map, left, right, top, bottomSnap }: Occluders) {
  const setMapInsets = useEphemeralStore((s) => s.setMapInsets);

  useLayoutEffect(() => {
    const container = map.current;
    if (!container) return;

    const measure = () => {
      const w = container.clientWidth;
      const h = container.clientHeight;
      // Still publish for an unsized map, so the queries it holds back run.
      if (!w || !h) {
        if (!sameInsets(NONE, useEphemeralStore.getState().mapInsets)) setMapInsets(NONE);
        return;
      }
      // The sheet is sized against the viewport; only the part above the
      // map's bottom edge covers it.
      const below = window.innerHeight - container.getBoundingClientRect().bottom;
      const sheet =
        bottomSnap == null ? 0 : snapCoverPx(bottomSnap, window.innerHeight) - below;
      const next: MapInsets = {
        top: quantize((top?.current?.offsetHeight ?? 0) / h),
        right: quantize((right?.current?.offsetWidth ?? 0) / w),
        bottom: quantize(Math.max(0, sheet) / h),
        left: quantize((left?.current?.offsetWidth ?? 0) / w),
      };
      if (!sameInsets(next, useEphemeralStore.getState().mapInsets)) setMapInsets(next);
    };

    measure();
    return observeResizes([container, left?.current, right?.current, top?.current], measure);
  }, [map, left, right, top, bottomSnap, setMapInsets]);
}

/** Debounced ResizeObserver over the given elements; returns the cleanup. */
function observeResizes(
  elements: (HTMLElement | null | undefined)[],
  onSettle: () => void,
): () => void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const observer = new ResizeObserver(() => {
    clearTimeout(timer);
    timer = setTimeout(onSettle, SETTLE_MS);
  });
  for (const el of elements) if (el) observer.observe(el);
  return () => {
    clearTimeout(timer);
    observer.disconnect();
  };
}
