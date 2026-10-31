import type { Map as MapLibreMap, MapLayerMouseEvent, PaddingOptions } from 'maplibre-gl';
import maplibregl from 'maplibre-gl';
import { useEffect, useMemo, useRef } from 'react';
import {
  useMapInstance,
  useMapStory,
  useReducedMotion,
  useSelection,
  useStoryNav,
  useStyleEpoch,
  useTimeState,
} from '@/hooks';
import { ease, resolveFrames, stepBounds, tween } from '@/lib/map-story/geometry';
import type { Frame } from '@/lib/map-story/geometry';
import { registerStoryImages } from '@/lib/map-story/icons';
import {
  addStoryLayers,
  moveCollection,
  noteCollection,
  removeStoryLayers,
  setEntityLayersVisible,
  setMoveOpacity,
  setSourceData,
  STORY_INTERACTIVE_LAYERS,
  STORY_SOURCES,
  terrainCollection,
  unitCollections,
} from '@/lib/map-story/layers';
import type { MapStoryDocument } from '@/lib/schemas/map-story';
import { useEphemeralStore } from '@/stores/ephemeral';
import type { MapInsets } from '@/types/atlas';

/** One step forward plays the movement; anything else glides quickly. */
const STEP_MS = 1600;
const JUMP_MS = 550;
const MAX_ZOOM = 15.5;

/** Keep the battle clear of the panels floating over the map. */
function padding(map: MapLibreMap, insets: MapInsets | null): PaddingOptions {
  const el = map.getContainer();
  const w = el.clientWidth;
  const h = el.clientHeight;
  const i = insets ?? { top: 0, right: 0, bottom: 0, left: 0 };
  const pad = {
    top: i.top * h + 48,
    right: i.right * w + 40,
    bottom: i.bottom * h + 40,
    left: i.left * w + 40,
  };
  // fitBounds misbehaves when padding leaves no room; shrink it to fit.
  const sx = Math.min(1, (w - 120) / (pad.left + pad.right));
  const sy = Math.min(1, (h - 120) / (pad.top + pad.bottom));
  return {
    top: pad.top * sy,
    bottom: pad.bottom * sy,
    left: pad.left * sx,
    right: pad.right * sx,
  };
}

function drawFrame(map: MapLibreMap, doc: MapStoryDocument, frame: Frame, focus: string[]): void {
  const { units, points } = unitCollections(doc, frame, focus);
  setSourceData(map, STORY_SOURCES.units, units);
  setSourceData(map, STORY_SOURCES.points, points);
}

/** A hover card for a unit: label, strength, commander, note. */
function unitCard(doc: MapStoryDocument, id: string): string | null {
  const unit = doc.units.find((u) => u.id === id);
  if (!unit) return null;
  const side = doc.sides.find((s) => s.id === unit.side);
  const esc = (s: string) => s.replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);
  const rows = [
    `<div style="display:flex;align-items:center;gap:6px;font-weight:600">` +
      `<span style="width:10px;height:10px;border-radius:2px;background:${esc(side?.color ?? '#555')}"></span>` +
      `${esc(unit.label)}</div>`,
    side ? `<div style="color:#57534e">${esc(side.name)} · ${esc(unit.kind.replace(/_/g, ' '))}</div>` : '',
    unit.strength ? `<div>Strength: ${esc(unit.strength)}</div>` : '',
    unit.commander ? `<div>Led by ${esc(unit.commander)}</div>` : '',
    unit.note ? `<div style="margin-top:4px;color:#44403c">${esc(unit.note)}</div>` : '',
  ];
  return `<div style="font:12px/1.4 system-ui,sans-serif;max-width:240px">${rows.join('')}</div>`;
}

/**
 * Draws the active battle map (URL `story`) on the shared map: hides the
 * entity overlay, adds terrain relief and the story's layers, frames each
 * step, and animates units from one step to the next — sliding them along
 * their arrows when they advance a single step. Renders no DOM.
 */
export function StoryOverlay() {
  const { map } = useMapInstance();
  const { styleEpoch } = useStyleEpoch();
  const { story, step } = useStoryNav();
  const { data } = useMapStory(story);
  const { setInstant } = useTimeState();
  const { select } = useSelection();
  const reduced = useReducedMotion();
  const insets = useEphemeralStore((s) => s.mapInsets);

  const doc = story && data?.slug === story ? data.document : null;
  const frames = useMemo(() => (doc ? resolveFrames(doc) : []), [doc]);
  const index = Math.min(Math.max(step, 0), Math.max(frames.length - 1, 0));

  /** What is on screen now (mid-animation too), and which step it shows. */
  const shownRef = useRef<{ frame: Frame; index: number } | null>(null);
  const rafRef = useRef<number>(0);
  // Latest values for the map's event handlers and the step animation.
  const insetsRef = useRef(insets);
  const selectRef = useRef(select);
  useEffect(() => {
    insetsRef.current = insets;
    selectRef.current = select;
  });

  // Jump the timeline (and the historical basemap) to the battle's year.
  useEffect(() => {
    if (doc) setInstant(doc.year);
  }, [doc, setInstant]);

  // ── layers: add on a new story or a rebuilt style; remove on exit ──────────
  useEffect(() => {
    if (!map || !doc) return;
    registerStoryImages(map, doc.sides.map((s) => s.color));
    addStoryLayers(map);
    setEntityLayersVisible(map, false);
    setSourceData(map, STORY_SOURCES.terrain, terrainCollection(doc));
    // A rebuilt style lost the units; redraw what was on screen.
    const shown = shownRef.current;
    if (shown) {
      drawFrame(map, doc, shown.frame, doc.steps[shown.index]?.focus ?? []);
      setSourceData(map, STORY_SOURCES.moves, moveCollection(doc, doc.steps[shown.index]));
      setSourceData(map, STORY_SOURCES.notes, noteCollection(doc.steps[shown.index]));
    }

    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12 });
    const onMove = (e: MapLayerMouseEvent) => {
      const id = e.features?.[0]?.properties?.id;
      const html = typeof id === 'string' ? unitCard(doc, id) : null;
      map.getCanvas().style.cursor = html ? 'pointer' : '';
      if (html) popup.setLngLat(e.lngLat).setHTML(html).addTo(map);
    };
    const onLeave = () => {
      map.getCanvas().style.cursor = '';
      popup.remove();
    };
    // A commander (or any unit) linked to an atlas entity opens its detail.
    const onClick = (e: MapLayerMouseEvent) => {
      const id = e.features?.[0]?.properties?.id;
      const unit = doc.units.find((u) => u.id === id);
      const entityId =
        unit?.entity_id ??
        (unit?.kind === 'commander'
          ? doc.sides.flatMap((s) => s.commanders).find((c) => c.name === unit.label)?.entity_id
          : null);
      if (entityId) void selectRef.current(entityId);
    };
    for (const layer of STORY_INTERACTIVE_LAYERS) {
      map.on('mousemove', layer, onMove);
      map.on('mouseleave', layer, onLeave);
      map.on('click', layer, onClick);
    }

    return () => {
      for (const layer of STORY_INTERACTIVE_LAYERS) {
        map.off('mousemove', layer, onMove);
        map.off('mouseleave', layer, onLeave);
        map.off('click', layer, onClick);
      }
      popup.remove();
      cancelAnimationFrame(rafRef.current);
      // The style may already be gone (unmount during teardown).
      if (map.style) {
        removeStoryLayers(map);
        setEntityLayersVisible(map, true);
      }
    };
  }, [map, doc, styleEpoch]);

  // Leaving the story forgets what was shown, so re-entering starts fresh.
  useEffect(() => {
    if (!doc) shownRef.current = null;
  }, [doc]);

  // ── step changes: frame the step and animate the units into place ─────────
  useEffect(() => {
    if (!map || !doc || frames.length === 0 || !map.getSource(STORY_SOURCES.units)) return;
    const target = frames[index];
    const stepDoc = doc.steps[index];
    const focus = stepDoc?.focus ?? [];
    const shown = shownRef.current;

    setSourceData(map, STORY_SOURCES.moves, moveCollection(doc, stepDoc));
    setSourceData(map, STORY_SOURCES.notes, noteCollection(stepDoc));

    // Camera: the step's own, else its units, arrows and notes.
    const pad = padding(map, insetsRef.current);
    const camera = stepDoc?.camera;
    if (camera) {
      map.flyTo({ center: camera.center, zoom: camera.zoom, bearing: camera.bearing ?? 0, padding: pad, duration: reduced ? 0 : 1100 });
    } else {
      const bounds = stepBounds(doc, target, index);
      if (bounds) map.fitBounds(bounds, { padding: pad, maxZoom: MAX_ZOOM, duration: reduced ? 0 : 1100 });
    }

    cancelAnimationFrame(rafRef.current);
    const from = shown?.frame;
    const forward = shown != null && index === shown.index + 1;
    if (!from || reduced || (shown && shown.index === index)) {
      drawFrame(map, doc, target, focus);
      setMoveOpacity(map, 1);
      shownRef.current = { frame: target, index };
      return;
    }

    const duration = forward ? STEP_MS : JUMP_MS;
    const moves = forward ? (stepDoc?.moves ?? []) : [];
    const start = performance.now();
    setMoveOpacity(map, forward ? 0 : 1);
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const frame = tween(from, target, moves, ease(t));
      drawFrame(map, doc, frame, focus);
      if (forward) setMoveOpacity(map, Math.min(1, t * 3));
      shownRef.current = { frame, index };
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [map, doc, frames, index, reduced, styleEpoch]);

  return null;
}
