import { useCallback, useSyncExternalStore } from 'react';

/** Reactive `matchMedia` boolean. SSR-safe (server snapshot = false). */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const mql = window.matchMedia(query);
      mql.addEventListener('change', onChange);
      return () => mql.removeEventListener('change', onChange);
    },
    [query],
  );
  const getSnapshot = () => window.matchMedia(query).matches;
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}

/** True on phones / small portrait tablets (Tailwind `md` boundary). */
export function useIsMobile(): boolean {
  return useMediaQuery('(max-width: 767px)');
}
