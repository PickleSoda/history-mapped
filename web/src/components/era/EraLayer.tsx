import { useEffect, useState } from 'react';
import { useMapInstance, useReducedMotion, useStyleEpoch } from '@/hooks';
import { applyEraToMap } from '@/lib/era/map-style';
import { useEra } from '@/lib/era/store';

/** How long the era's name stays up after the map enters it. */
const ANNOUNCE_MS = 2600;

/**
 * Names the era when the map enters it, like a chapter heading, then fades.
 * Silent for the first era after the page opens.
 */
function EraAnnouncer() {
  const reduced = useReducedMotion();
  const [label, setLabel] = useState<string | null>(null);
  const [show, setShow] = useState(false);

  useEffect(() => {
    let seen = useEra.getState().entry?.id ?? null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const unsubscribe = useEra.subscribe(({ entry }) => {
      if (!entry || entry.id === seen) return;
      const first = seen === null;
      seen = entry.id;
      if (first) return;
      setLabel(entry.label);
      setShow(true);
      clearTimeout(timer);
      timer = setTimeout(() => setShow(false), ANNOUNCE_MS);
    });
    return () => {
      unsubscribe();
      clearTimeout(timer);
    };
  }, []);

  return (
    <div
      role="status"
      aria-live="polite"
      data-show={show}
      data-motion={reduced ? 'reduced' : 'full'}
      className="era-announce pointer-events-none absolute left-1/2 top-4 z-[5] rounded-lg border bg-card/90 px-5 pb-2 pt-1.5 text-center shadow-sm backdrop-blur"
    >
      <div className="font-heading text-lg leading-tight">{label}</div>
      <div aria-hidden className="mx-auto mt-1 h-0.5 w-12 rounded-full bg-[var(--era-ornament)]" />
    </div>
  );
}

/**
 * The era's layer on the map: restyles the basemap's borders, land and sea
 * for the active era (again after every basemap switch), darkens the edges
 * with the era's tint, and announces era changes. Renders inside the map.
 */
export function EraLayer() {
  const { map } = useMapInstance();
  const { styleEpoch } = useStyleEpoch();
  const theme = useEra((s) => s.theme);

  useEffect(() => {
    if (!map) return;
    try {
      applyEraToMap(map, theme);
    } catch (error) {
      // A style mid-swap rejects paint changes; the next style epoch retries.
      console.warn('[era] map styling skipped', error);
    }
  }, [map, styleEpoch, theme]);

  return (
    <>
      <div aria-hidden className="era-vignette" />
      <EraAnnouncer />
    </>
  );
}
