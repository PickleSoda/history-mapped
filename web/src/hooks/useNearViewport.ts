import { useEffect, useState } from 'react';
import type { RefObject } from 'react';
import { nextMounted } from '@/lib/chronicle-page';

/**
 * True while `ref`'s element is near the visible part of `root` (a scroll
 * container), with hysteresis: it turns true within `near` px of the viewport
 * and false only beyond `far` px. Lazily mounted heavy children (step graphs)
 * key off it. `root` must be the actual scroll container — margins don't
 * extend past an ancestor's clip.
 */
export function useNearViewport(
  ref: RefObject<Element | null>,
  root: Element | null,
  { near = 400, far = 1400 }: { near?: number; far?: number } = {},
): boolean {
  const [on, setOn] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || !root) return;
    const zones: { near: boolean | null; far: boolean | null } = { near: null, far: null };
    const update = () => setOn((prev) => nextMounted(prev, zones));
    const nearIo = new IntersectionObserver(
      ([e]) => {
        zones.near = e.isIntersecting;
        update();
      },
      { root, rootMargin: `${near}px 0px` },
    );
    const farIo = new IntersectionObserver(
      ([e]) => {
        zones.far = e.isIntersecting;
        update();
      },
      { root, rootMargin: `${far}px 0px` },
    );
    nearIo.observe(el);
    farIo.observe(el);
    return () => {
      nearIo.disconnect();
      farIo.disconnect();
    };
  }, [ref, root, near, far]);
  return on;
}
