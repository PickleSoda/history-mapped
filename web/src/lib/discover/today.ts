/**
 * The reader's local day as React state. A tab left open overnight moves on
 * to the new day by itself: at the next local midnight, and whenever the tab
 * is looked at again (a sleeping laptop fires no timers).
 */
import { useSyncExternalStore } from 'react';
import { dayKey } from './date';

function subscribe(onChange: () => void): () => void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const arm = () => {
    const now = new Date();
    const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    timer = setTimeout(
      () => {
        onChange();
        arm();
      },
      midnight.getTime() - now.getTime() + 500,
    );
  };
  arm();
  document.addEventListener('visibilitychange', onChange);
  window.addEventListener('focus', onChange);
  return () => {
    clearTimeout(timer);
    document.removeEventListener('visibilitychange', onChange);
    window.removeEventListener('focus', onChange);
  };
}

const today = () => dayKey();

/** Today as a local `YYYY-MM-DD` key (see `dayKey`), re-read when the day turns. */
export function useToday(): string {
  return useSyncExternalStore(subscribe, today, today);
}
