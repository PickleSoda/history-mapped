import type { FeatureCollection } from 'geojson';
import type { MapLayerMouseEvent } from 'maplibre-gl';
import maplibregl from 'maplibre-gl';
import { useEffect, useMemo, useRef } from 'react';
import {
  useChronicle,
  useChronicleNav,
  useChroniclePlaces,
  useMapInstance,
  useReducedMotion,
  useSelection,
  useStoryNav,
  useStyleEpoch,
} from '@/hooks';
import { useActiveStory } from '@/hooks/useMapStory';
import {
  addChronicleLayers,
  CHRONICLE_SOURCES,
  fadeEntityLayers,
  forgetFade,
  removeChronicleLayers,
  setChronicleAreas,
  setChronicleData,
  setGlow,
  setPulse,
  setReveal,
} from '@/lib/chronicle-map/layers';
import { placesIndex, stepScene, trailCollection, trailStops } from '@/lib/chronicle-map/scene';
import { formatYear } from '@/lib/format';

/** The arc grows over the camera's flight to the step (useMapFocus flies for 900 ms). */
const REVEAL_MS = 1000;
/** One pass of the glow along the arc, and one ripple at the anchor. */
const GLOW_MS = 2600;
const PULSE_MS = 1900;
/** Paint updates at most this often (they redraw the map, not reload data). */
const FRAME_MS = 33;

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] };
const esc = (s: string) => s.replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);

/** The first sentence of a narrative, cut to `max` characters. */
function lead(text: string | null | undefined, max = 110): string {
  if (!text) return '';
  const first = text.split(/(?<=[.!?])\s/)[0] ?? text;
  return first.length > max ? `${first.slice(0, max - 1).trimEnd()}…` : first;
}

/**
 * The playing chronicle's step on the map: its relationship as an animated
 * arc in the colour of its kind (a fight, a spread, a succession…), its
 * entities as markers joined to where the step happens, the borders of its
 * polities as they stood that year, and the numbered trail of the steps
 * before it (click a stop to go back to it). The atlas's other markers fade
 * meanwhile. A chronicle's own map layer, where it has a step for the entry,
 * draws that step instead (only the trail stays).
 */
export function ChronicleLayer() {
  const { map } = useMapInstance();
  const { styleEpoch } = useStyleEpoch();
  const { chron, step, goto } = useChronicleNav();
  const { isActive: storyActive } = useStoryNav();
  const { data: chronicle } = useChronicle(chron);
  const { data: placeList } = useChroniclePlaces(chron);
  const active = useActiveStory();
  const { select } = useSelection();
  const reduced = useReducedMotion();

  const on = chron !== null && !storyActive && chronicle != null && placeList != null;
  const places = useMemo(() => placesIndex(placeList), [placeList]);
  const entries = useMemo(() => chronicle?.entries ?? [], [chronicle]);
  const entry = on ? entries[step] : undefined;
  const layerStep = active?.mode === 'chronicle' && active.index != null;
  const scene = useMemo(() => (entry && !layerStep ? stepScene(entry, places) : null), [entry, layerStep, places]);
  const trail = useMemo(
    () => (on ? trailCollection(trailStops(entries, places, step), step) : EMPTY),
    [on, entries, places, step],
  );
  const year = entry?.start_year ?? null;

  // Latest values for the map's event handlers.
  const gotoRef = useRef(goto);
  const selectRef = useRef(select);
  const entriesRef = useRef(entries);
  useEffect(() => {
    gotoRef.current = goto;
    selectRef.current = select;
    entriesRef.current = entries;
  });

  // ── layers: added while a chronicle plays, re-added on a rebuilt style ──
  useEffect(() => {
    // `map.style` is gone once a map is removed: crossing the phone breakpoint
    // remounts MapCanvas, and this effect can still hold the map before it.
    if (!map || !map.style || !on) return;
    forgetFade(map);
    addChronicleLayers(map);
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12, maxWidth: '260px' });
    const onStopMove = (e: MapLayerMouseEvent) => {
      const index = e.features?.[0]?.properties?.step;
      const entry = typeof index === 'number' ? entriesRef.current[index] : undefined;
      if (!entry) return;
      map.getCanvas().style.cursor = 'pointer';
      const when = entry.start_year != null ? ` · ${esc(formatYear(entry.start_year))}` : '';
      popup
        .setLngLat(e.lngLat)
        .setHTML(
          `<div style="font:12px/1.4 system-ui,sans-serif"><b>Step ${index + 1}</b>${when}` +
            `<div style="color:#44403c;margin-top:2px">${esc(lead(entry.narrative_text))}</div></div>`,
        )
        .addTo(map);
    };
    const onEnter = () => {
      map.getCanvas().style.cursor = 'pointer';
    };
    const onLeave = () => {
      map.getCanvas().style.cursor = '';
      popup.remove();
    };
    // MapCanvas leaves clicks on these layers to us.
    const onStopClick = (e: MapLayerMouseEvent) => {
      const index = e.features?.[0]?.properties?.step;
      e.preventDefault();
      popup.remove();
      if (typeof index === 'number') gotoRef.current(index);
    };
    const onCastClick = (e: MapLayerMouseEvent) => {
      const id = e.features?.[0]?.properties?.id;
      e.preventDefault();
      if (typeof id === 'string' && id) void selectRef.current(id);
    };
    map.on('mousemove', 'chron-trail-stop', onStopMove);
    map.on('mouseleave', 'chron-trail-stop', onLeave);
    map.on('click', 'chron-trail-stop', onStopClick);
    map.on('mouseenter', 'chron-cast', onEnter);
    map.on('mouseleave', 'chron-cast', onLeave);
    map.on('click', 'chron-cast', onCastClick);
    return () => {
      map.off('mousemove', 'chron-trail-stop', onStopMove);
      map.off('mouseleave', 'chron-trail-stop', onLeave);
      map.off('click', 'chron-trail-stop', onStopClick);
      map.off('mouseenter', 'chron-cast', onEnter);
      map.off('mouseleave', 'chron-cast', onLeave);
      map.off('click', 'chron-cast', onCastClick);
      popup.remove();
      // The style may already be gone (unmount during teardown).
      if (map.style) {
        removeChronicleLayers(map);
        fadeEntityLayers(map, null);
      }
    };
  }, [map, on, styleEpoch]);

  // ── the step: its scene, its borders at its year, the trail; the atlas fades ──
  useEffect(() => {
    if (!map || !map.style || !on || !map.getSource(CHRONICLE_SOURCES.points)) return;
    setChronicleData(map, scene, trail);
    setChronicleAreas(map, scene?.areas ?? null, year, scene?.color ?? '#4338ca');
    fadeEntityLayers(map, scene ? scene.cast.map((m) => m.id) : null);
  }, [map, on, scene, trail, year, styleEpoch]);

  // ── the arc grows from its source, then a glow travels it; the anchor ripples ──
  useEffect(() => {
    if (!map || !map.style || !on || !scene || !map.getSource(CHRONICLE_SOURCES.points)) return;
    const { color } = scene;
    const soft = scene.arc?.properties.soft ?? false;
    if (reduced) {
      setReveal(map, color, 1, soft);
      setPulse(map, 0.35);
      return;
    }
    setReveal(map, color, 0, soft);
    const glows = scene.arc != null && !scene.arc.properties.dashed;
    const start = performance.now();
    let last = 0;
    let revealed = false;
    let raf = requestAnimationFrame(function tick(now) {
      raf = requestAnimationFrame(tick);
      if (now - last < FRAME_MS) return;
      last = now;
      // A frame's timestamp can precede `start` (it is when the frame began).
      const t = Math.max(0, now - start);
      if (t < REVEAL_MS) {
        setReveal(map, color, 1 - (1 - t / REVEAL_MS) ** 3, soft);
      } else {
        if (!revealed) {
          revealed = true;
          setReveal(map, color, 1, soft);
        }
        if (glows) setGlow(map, color, ((t - REVEAL_MS) % GLOW_MS) / GLOW_MS, soft);
      }
      setPulse(map, (t % PULSE_MS) / PULSE_MS);
    });
    return () => cancelAnimationFrame(raf);
  }, [map, on, scene, reduced, styleEpoch]);

  return null;
}
