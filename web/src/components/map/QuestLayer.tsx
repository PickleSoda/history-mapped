import { Check, Compass } from 'lucide-react';
import maplibregl from 'maplibre-gl';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { PlaceMeter, Stars, TimeMeter, YearsHidden } from '@/components/discover/QuestMeter';
import {
  useAtlasGo,
  useChronicleNav,
  useDailyQuest,
  useMapInstance,
  useOpenBrowseTab,
  useStoryNav,
  useTimeState,
} from '@/hooks';
import { clueText, MAX_STARS, NO_PROGRESS, sameLevels, sameReading, starsFor, takeReading, tally } from '@/lib/discover/quest';
import type { QuestReading } from '@/lib/discover/quest';
import { readMapView } from '@/lib/discover/quest-map';
import { useQuestDay, useQuestLive, useQuestStore } from '@/lib/discover/quest-store';
import { instantYear } from '@/lib/format';
import { useEphemeralStore } from '@/stores/ephemeral';
import type { MapInsets } from '@/types/atlas';

/** While only the distance changes (not a warmth), it reaches the screen at most this often. */
const DISTANCE_MS = 150;
/** How long "Found" stays over the map after the marker is clicked. */
const FOUND_MS = 6000;
const NO_INSETS: MapInsets = { top: 0, right: 0, bottom: 0, left: 0 };

/** What the strip says once a target is found. */
interface FoundNote {
  name: string;
  stars: number;
  /** The day so far. */
  found: number;
  of: number;
  dayStars: number;
  complete: boolean;
}

/**
 * The found-it marker: a ring on the target, in fixed colours (the basemaps
 * are light in both themes), sending out ripples (the `quest-*` rules in
 * styles.css; none under reduced motion). A real button, so it can be reached
 * and pressed from the keyboard. MapLibre moves its root with an inline
 * transform, so the look and the motion are on its children.
 */
function markerElement(name: string): HTMLButtonElement {
  const el = document.createElement('button');
  el.type = 'button';
  el.className = 'group grid size-11 cursor-pointer place-items-center rounded-full outline-none';
  el.setAttribute('aria-label', `${name}: you are there. Mark it found`);
  el.title = 'You are there. Click to mark it found';
  const ripple = 'quest-ripple pointer-events-none absolute inset-0 m-auto size-7 rounded-full border-2 border-[#0b7a55]';
  const ring =
    'quest-ring relative size-7 rounded-full border-[3px] border-[#0b7a55] bg-[#0b7a55]/15 transition-colors group-hover:bg-[#0b7a55]/40 group-focus-visible:bg-[#0b7a55]/40 group-focus-visible:outline-2 group-focus-visible:outline-offset-4 group-focus-visible:outline-[#0b7a55]';
  for (const className of [ripple, ripple, ring]) {
    const part = document.createElement('span');
    part.className = className;
    el.appendChild(part);
  }
  // A white edge inside and out keeps the ring legible on any basemap.
  (el.lastChild as HTMLElement).style.boxShadow = '0 0 0 2px #fff, inset 0 0 0 1.5px #fff, 0 1px 6px rgba(0, 0, 0, 0.4)';
  return el;
}

/**
 * The strip: top centre of the part of the map the panels leave visible. One
 * line where there is room (what it is about, how things stand, the button);
 * on a map as narrow as a phone's the button moves up beside the name and the
 * rest takes a second line. Clicks pass through it to the map, except on the
 * button.
 */
function Strip({ lead, action, children }: { lead: ReactNode; action: ReactNode; children: ReactNode }) {
  const insets = useEphemeralStore((s) => s.mapInsets) ?? NO_INSETS;
  return (
    <div
      className="pointer-events-none absolute z-[5] flex justify-center px-2 sm:px-4"
      style={{
        top: `calc(${insets.top * 100}% + 12px)`,
        left: `${insets.left * 100}%`,
        right: `${insets.right * 100}%`,
      }}
    >
      <div className="flex max-w-full flex-wrap items-center justify-center gap-x-3 gap-y-1 rounded-2xl border bg-card/95 px-3 py-1.5 text-[12px] text-foreground shadow-md backdrop-blur motion-safe:animate-in motion-safe:fade-in">
        <span className="flex min-w-0 flex-1 items-center gap-1.5 font-semibold sm:flex-none">{lead}</span>
        <span className="order-last flex basis-full flex-wrap items-center justify-center gap-x-3 gap-y-1 sm:order-none sm:basis-auto">
          {children}
        </span>
        {action}
      </div>
    </div>
  );
}

/** The strip's one control: everything else lets clicks through to the map. */
function TodayButton({ children }: { children: string }) {
  const openTab = useOpenBrowseTab();
  return (
    <button
      type="button"
      onClick={() => openTab('today')}
      title="Open the expedition in the Today tab"
      className="pointer-events-auto flex-none rounded-full border bg-card px-2.5 py-0.5 text-[11px] font-medium transition-colors hover:bg-muted"
    >
      {children}
    </button>
  );
}

/**
 * One target being looked for. Reads the map and the timeline, publishes how
 * the reader stands to it (`useQuestLive`), shows the strip, and puts the
 * marker on the map once they have arrived. Mounted per target (keyed by its
 * id), so every listener and the marker go when the target changes.
 */
function QuestHunt({ id, onFound }: { id: string; onFound: (note: FoundNote) => void }) {
  const { map } = useMapInstance();
  const today = useQuestDay();
  const { data: quest } = useDailyQuest(today);
  const { time } = useTimeState();
  const { isActive: chronicleActive } = useChronicleNav();
  const { isActive: storyActive } = useStoryNav();
  const insets = useEphemeralStore((s) => s.mapInsets);
  const go = useAtlasGo();
  const progress = useQuestStore((s) => s.targets[id]);
  const hasReading = useQuestLive((s) => s.reading?.id === id);
  const arrived = useQuestLive((s) => s.reading?.id === id && s.reading.arrived);

  const year = instantYear(time);
  // A chronicle or a battle map has the map and the timeline to itself.
  const playing = chronicleActive || storyActive;
  const target = (!playing && quest?.targets.find((t) => t.id === id)) || null;

  // Latest values for the map's handlers and the marker's click.
  const latest = useRef({ year, insets, quest, go, onFound });
  useEffect(() => {
    latest.current = { year, insets, quest, go, onFound };
  });

  // ── read the map and the timeline; publish only what changed ──────────────
  const readNow = useRef<() => void>(() => {});
  useEffect(() => {
    if (!target) return;
    const { publish, clear } = useQuestLive.getState();
    let frame = 0;
    let held: QuestReading | null = null;
    let heldAt = 0;
    const read = (settled: boolean) => {
      frame = 0;
      const committed = latest.current.year;
      const next = takeReading(
        target,
        // The warmth follows the timeline while it is dragged; arriving waits for the year the map is at.
        { shown: useEphemeralStore.getState().liveScrub ?? committed, committed },
        map ? readMapView(map, latest.current.insets, target.at) : null,
      );
      if (held && sameReading(held, next)) return;
      const now = performance.now();
      // Only the distance moved: a few times a second is enough, and once more when the map rests.
      if (held && sameLevels(held, next) && !settled && now - heldAt < DISTANCE_MS) return;
      held = next;
      heldAt = now;
      publish(next);
    };
    // The camera moves every frame; read it once per frame at most.
    const onMove = () => {
      if (!frame) frame = requestAnimationFrame(() => read(false));
    };
    const onRest = () => {
      cancelAnimationFrame(frame);
      read(true);
    };
    map?.on('move', onMove);
    map?.on('moveend', onRest);
    const unsubscribe = useEphemeralStore.subscribe((s, before) => {
      if (s.liveScrub !== before.liveScrub) onMove();
    });
    readNow.current = onRest;
    read(true);
    return () => {
      map?.off('move', onMove);
      map?.off('moveend', onRest);
      unsubscribe();
      cancelAnimationFrame(frame);
      readNow.current = () => {};
      clear();
    };
  }, [map, target]);

  // The year the map is at changed, or the panels over the map did: read again.
  useEffect(() => {
    readNow.current();
  }, [year, insets]);

  // ── the marker: on the map on arrival, off it otherwise ───────────────────
  useEffect(() => {
    if (!map || !target || !arrived) return;
    const element = markerElement(target.name);
    const onClick = (event: MouseEvent) => {
      // The map must not take the click for one of its own (it would open whatever lies under the ring).
      event.stopPropagation();
      const { quest, go, onFound } = latest.current;
      const ids = quest?.targets.map((t) => t.id) ?? [target.id];
      useQuestStore.getState().find(target.id, ids);
      const { targets } = useQuestStore.getState();
      const day = tally(ids, targets);
      onFound({
        name: target.name,
        stars: starsFor(targets[target.id] ?? NO_PROGRESS),
        found: day.found,
        of: ids.length,
        dayStars: day.stars,
        complete: day.complete,
      });
      go({ id: target.id });
    };
    element.addEventListener('click', onClick);
    const marker = new maplibregl.Marker({ element }).setLngLat(target.at).addTo(map);
    return () => {
      element.removeEventListener('click', onClick);
      marker.remove();
    };
  }, [map, target, arrived]);

  if (!target || !hasReading) return null;
  return (
    <Strip
      lead={
        <>
          <Compass size={13} aria-hidden className="flex-none text-muted-foreground" />
          <span className="min-w-0 truncate sm:max-w-[15rem]">
            <YearsHidden text={clueText(target.name, target, progress)} />
          </span>
        </>
      }
      action={<TodayButton>Hints</TodayButton>}
    >
      {arrived ? (
        <span role="status" className="flex items-center gap-1 font-medium motion-safe:animate-in motion-safe:fade-in">
          <Check size={13} strokeWidth={3} aria-hidden className="flex-none text-[#199e70]" />
          Right place, right time. Click the ring.
        </span>
      ) : (
        <>
          <TimeMeter id={id} />
          <PlaceMeter id={id} />
        </>
      )}
    </Strip>
  );
}

/** For a few seconds after a find: what it earned, and the way to the next one. */
function FoundStrip({ note, onDone }: { note: FoundNote; onDone: () => void }) {
  const { isActive: chronicleActive } = useChronicleNav();
  const { isActive: storyActive } = useStoryNav();
  useEffect(() => {
    const timer = setTimeout(onDone, FOUND_MS);
    return () => clearTimeout(timer);
  }, [note, onDone]);
  if (chronicleActive || storyActive) return null;
  return (
    <Strip
      lead={
        <>
          <Check size={13} strokeWidth={3} aria-hidden className="flex-none text-[#199e70]" />
          <span role="status" className="min-w-0 truncate sm:max-w-[15rem]">
            Found: {note.name}
          </span>
        </>
      }
      action={<TodayButton>{note.complete ? 'Result' : 'Next'}</TodayButton>}
    >
      <Stars count={note.stars} />
      <span className="text-muted-foreground">
        {note.complete
          ? `Expedition complete, ${note.dayStars} of ${note.of * MAX_STARS} stars`
          : `${note.found} of ${note.of} found`}
      </span>
    </Strip>
  );
}

/**
 * The daily expedition on the map: while a target is being looked for, a
 * small strip over the map saying how warm the reader is in time and in
 * place, and, once they have reached both, a pulsing ring on the target that
 * completes it when clicked. Mounted inside MapCanvas. With no target active
 * it holds one store subscription and nothing else.
 */
export function QuestLayer() {
  const active = useQuestStore((s) => s.active);
  const [found, setFound] = useState<FoundNote | null>(null);
  const forget = useCallback(() => setFound(null), []);
  // The next target is under way: the last find has had its moment.
  if (active != null && found) setFound(null);
  return (
    <>
      {active != null && <QuestHunt key={active} id={active} onFound={setFound} />}
      {active == null && found && <FoundStrip note={found} onDone={forget} />}
    </>
  );
}
