import { ArrowUp, Moon, Sun, Sunrise, Sunset, Wind } from 'lucide-react';
import type { Map as MapLibreMap, MapLayerMouseEvent, PaddingOptions } from 'maplibre-gl';
import maplibregl from 'maplibre-gl';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import {
  useMapInstance,
  useMapStory,
  useReducedMotion,
  useSelection,
  useStoryNav,
  useStyleEpoch,
  useTimeState,
} from '@/hooks';
import { storyPalette, unitColor } from '@/lib/map-story/colors';
import {
  ease,
  onField,
  resolveBeatFrames,
  resolveConditions,
  resolveTerrainState,
  stepBounds,
  stepPhases,
  tweener,
} from '@/lib/map-story/geometry';
import type { Conditions, Frame, Resolved } from '@/lib/map-story/geometry';
import { registerStoryImages } from '@/lib/map-story/icons';
import {
  addStoryLayers,
  altSiteCollection,
  holdCollection,
  maskCollection,
  moveCollection,
  moveTails,
  noteCollection,
  removeStoryLayers,
  setEntityLayersVisible,
  setLight,
  setMoveOpacity,
  setSourceData,
  STORY_INTERACTIVE_LAYERS,
  STORY_SOURCES,
  terrainCollection,
  unitCollections,
} from '@/lib/map-story/layers';
import type { MoveTail } from '@/lib/map-story/layers';
import type { LngLat, MapStoryDocument } from '@/lib/schemas/map-story';
import { useEphemeralStore } from '@/stores/ephemeral';
import type { MapInsets } from '@/types/atlas';

/** One step forward plays the movement, then each beat; anything else glides quickly. */
const STEP_MS = 1600;
const BEAT_MS = 1200;
const JUMP_MS = 550;
/** How long the last beat's caption stays once the step has played. */
const CAPTION_LINGER_MS = 2200;
const MAX_ZOOM = 15.5;
const NO_INSETS: MapInsets = { top: 0, right: 0, bottom: 0, left: 0 };

/** Keep the battle clear of the panels floating over the map. */
function padding(map: MapLibreMap, insets: MapInsets | null): PaddingOptions {
  const el = map.getContainer();
  const w = el.clientWidth;
  const h = el.clientHeight;
  const i = insets ?? NO_INSETS;
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

const STATE_TEXT: Record<string, string> = {
  engaged: 'Engaged',
  wavering: 'Wavering',
  routed: 'Routed',
  destroyed: 'Destroyed',
  killed: 'Killed',
  wounded: 'Wounded',
  captured: 'Captured',
  sunk: 'Sunk',
  aground: 'Aground',
  burning: 'On fire',
};

/** A hover card for a unit: label, side and contingent, strength, state, commander, note. */
function unitCard(doc: MapStoryDocument, id: string, r: Resolved | undefined): string | null {
  const unit = doc.units.find((u) => u.id === id);
  if (!unit) return null;
  const side = doc.sides.find((s) => s.id === unit.side);
  const contingent = side?.contingents.find((c) => c.id === unit.contingent);
  const esc = (s: string) => s.replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);
  const strength = r?.strength ?? unit.strength;
  const count = r?.strength_n ?? unit.strength_n;
  const strengthText = [strength, count != null && !strength ? count.toLocaleString() : null, count != null && strength ? `≈ ${count.toLocaleString()}` : null]
    .filter(Boolean)
    .join(' · ');
  const captor = r?.state === 'captured' && r.by ? doc.sides.find((s) => s.id === r.by)?.name : null;
  const state = r && STATE_TEXT[r.state] ? `${STATE_TEXT[r.state]}${captor ? ` by ${captor}` : ''}` : '';
  const rows = [
    `<div style="display:flex;align-items:center;gap:6px;font-weight:600">` +
      `<span style="width:10px;height:10px;border-radius:2px;background:${esc(side ? unitColor(side, unit) : '#555')}"></span>` +
      `${esc(r?.label ?? unit.label)}</div>`,
    side
      ? `<div style="color:#57534e">${esc(side.name)}${contingent ? ` · ${esc(contingent.name)}` : ''} · ${esc(unit.kind.replace(/_/g, ' '))}</div>`
      : '',
    strengthText ? `<div>Strength: ${esc(strengthText)}</div>` : '',
    state ? `<div style="font-weight:600;color:#7c2d12">${esc(state)}</div>` : '',
    r?.conjectural ? `<div style="color:#78716c;font-style:italic">Position conjectural</div>` : '',
    unit.commander ? `<div>Led by ${esc(unit.commander)}</div>` : '',
    unit.note ? `<div style="margin-top:4px;color:#44403c">${esc(unit.note)}</div>` : '',
  ];
  return `<div style="font:12px/1.4 system-ui,sans-serif;max-width:240px">${rows.join('')}</div>`;
}

/** The farthest point of segment a→b inside `rect` (Liang–Barsky), or null if it never enters. */
function clipEnd(
  a: { x: number; y: number },
  b: { x: number; y: number },
  rect: { l: number; r: number; t: number; b: number },
): { x: number; y: number } | null {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  let t0 = 0;
  let t1 = 1;
  for (const [p, q] of [
    [-dx, a.x - rect.l],
    [dx, rect.r - a.x],
    [-dy, a.y - rect.t],
    [dy, rect.b - a.y],
  ]) {
    if (p === 0) {
      if (q < 0) return null;
    } else if (p < 0) t0 = Math.max(t0, q / p);
    else t1 = Math.min(t1, q / p);
  }
  return t0 > t1 ? null : { x: a.x + dx * t1, y: a.y + dy * t1 };
}

const CHEVRON =
  '<svg viewBox="0 0 10 10" width="10" height="10" aria-hidden="true"><path d="M3.5 1.5 L7 5 L3.5 8.5" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

/**
 * Edge markers, positioned imperatively (no React render per map move):
 * a chevron on the viewport edge, in its colour, for each unit off screen
 * (click to pan to it), and the edge label of each `continues` tail.
 */
function placeMarkers(
  map: MapLibreMap,
  host: HTMLDivElement,
  frame: Frame | undefined,
  units: Map<string, { color: string; label: string }>,
  tails: MoveTail[],
  insets: MapInsets | null,
  reduced: boolean,
): void {
  const w = host.clientWidth;
  const h = host.clientHeight;
  const i = insets ?? NO_INSETS;
  const rect = { l: i.left * w + 14, r: w - i.right * w - 14, t: i.top * h + 14, b: h - i.bottom * h - 14 };
  const cx = (rect.l + rect.r) / 2;
  const cy = (rect.t + rect.b) / 2;
  const chevrons = host.querySelectorAll<HTMLButtonElement>('[data-chevron]');
  const labels = host.querySelectorAll<HTMLDivElement>('[data-tail]');
  let used = 0;

  for (const [uid, r] of frame ?? []) {
    const info = units.get(uid);
    if (!info || r.with || !onField(r) || (r.fade ?? 1) < 0.5) continue;
    const p = map.project(r.at);
    if (p.x >= rect.l && p.x <= rect.r && p.y >= rect.t && p.y <= rect.b) continue;
    // Where the ray from the view's centre to the unit leaves the view.
    const dx = p.x - cx;
    const dy = p.y - cy;
    const s = Math.min(dx ? (dx > 0 ? rect.r - cx : rect.l - cx) / dx : Infinity, dy ? (dy > 0 ? rect.b - cy : rect.t - cy) / dy : Infinity);
    let el = chevrons[used];
    if (!el) {
      el = document.createElement('button');
      el.type = 'button';
      el.dataset.chevron = '';
      el.className = 'pointer-events-auto absolute left-0 top-0 grid size-5 place-items-center rounded-full border-2 border-white shadow-md';
      el.innerHTML = CHEVRON;
      host.appendChild(el);
    }
    used++;
    const label = r.label ?? info.label;
    el.style.display = '';
    el.style.background = info.color;
    el.style.transform = `translate(${cx + dx * s - 10}px, ${cy + dy * s - 10}px) rotate(${Math.atan2(dy, dx)}rad)`;
    el.title = label;
    el.setAttribute('aria-label', `${label} (off screen)`);
    el.onclick = () => map.easeTo({ center: r.at as LngLat, duration: reduced ? 0 : 600 });
  }
  for (let k = used; k < chevrons.length; k++) chevrons[k].style.display = 'none';

  // Tail labels sit where the tail leaves the view, or at its far end if that's in view.
  const inner = { l: rect.l + 56, r: rect.r - 56, t: rect.t + 10, b: rect.b - 10 };
  let shown = 0;
  for (const tail of tails) {
    const at = clipEnd(map.project(tail.from), map.project(tail.toward), inner);
    if (!at) continue;
    let el = labels[shown];
    if (!el) {
      el = document.createElement('div');
      el.dataset.tail = '';
      el.className = 'absolute left-0 top-0 whitespace-nowrap text-[11px] font-semibold italic';
      el.style.textShadow = '0 0 3px #fffdf5, 0 0 3px #fffdf5, 0 0 2px #fffdf5';
      host.appendChild(el);
    }
    shown++;
    el.style.display = '';
    el.style.color = tail.color;
    el.style.transform = `translate(${at.x}px, ${at.y}px) translate(-50%, -50%)`;
    el.textContent = tail.label;
  }
  for (let k = shown; k < labels.length; k++) labels[k].style.display = 'none';
}

const COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
const compass = (deg: number) => COMPASS[Math.round((((deg % 360) + 360) % 360) / 45) % 8];

/** A row of the wind/sun widget: an arrow pointing the way it blows or shines. */
function HudRow({ icon, toward, text }: { icon: ReactNode; toward: number | null; text: string }) {
  return (
    <div className="flex items-center gap-1.5">
      {icon}
      {toward != null && (
        <ArrowUp size={14} strokeWidth={2.5} style={{ transform: `rotate(calc(${toward}deg - var(--map-bearing, 0deg)))` }} />
      )}
      <span className="max-w-[260px] truncate" title={text}>{text}</span>
    </div>
  );
}

const LIGHT_ICON = { night: Moon, dawn: Sunrise, dusk: Sunset } as const;

function Hud({ conditions }: { conditions: Conditions }) {
  const { light, wind, sun } = conditions;
  if (light === 'day' && !wind && !sun) return null;
  const LightIcon = light !== 'day' ? LIGHT_ICON[light] : null;
  return (
    <div className="space-y-1 rounded-lg border bg-card/90 px-2.5 py-1.5 text-[11px] text-foreground shadow-sm backdrop-blur">
      {LightIcon && <HudRow icon={<LightIcon size={13} />} toward={null} text={light[0].toUpperCase() + light.slice(1)} />}
      {wind && (
        <HudRow
          icon={<Wind size={13} />}
          toward={wind.from + 180}
          text={wind.label ?? `${wind.strength === 'strong' ? 'Strong wind' : wind.strength === 'light' ? 'Light wind' : 'Wind'} from the ${compass(wind.from)}`}
        />
      )}
      {sun && <HudRow icon={<Sun size={13} />} toward={sun.from + 180} text={sun.label ?? `Sun in the ${compass(sun.from)}`} />}
    </div>
  );
}

/**
 * Draws the active battle map (URL `story`) on the shared map: hides the
 * entity overlay, adds terrain relief and the story's layers, frames each
 * step, and animates units from one step to the next — sliding them along
 * their arrows when they advance a single step, then playing the step's beats
 * with a caption. Its DOM is a thin layer over the map: off-screen chevrons,
 * tail labels, the beat caption and the wind/sun widget.
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
  const phases = useMemo(() => (doc ? resolveBeatFrames(doc) : []), [doc]);
  const frames = useMemo(() => phases.map((p) => p[p.length - 1]), [phases]);
  const holds = useMemo(() => (doc ? resolveTerrainState(doc) : []), [doc]);
  const conditions = useMemo(() => (doc ? resolveConditions(doc) : []), [doc]);
  const unitInfo = useMemo(() => {
    const out = new Map<string, { color: string; label: string }>();
    for (const u of doc?.units ?? []) {
      const side = doc?.sides.find((s) => s.id === u.side);
      if (side) out.set(u.id, { color: unitColor(side, u), label: u.label });
    }
    return out;
  }, [doc]);
  const index = Math.min(Math.max(step, 0), Math.max(frames.length - 1, 0));

  /** What is on screen now (mid-animation too): the frame, its step and phase. */
  const shownRef = useRef<{ frame: Frame; index: number; phase: number } | null>(null);
  const tailsRef = useRef<MoveTail[]>([]);
  const markersRef = useRef<HTMLDivElement>(null);
  const hudRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number>(0);
  /** Re-place the edge markers now (they also follow every camera move). */
  const placeRef = useRef<() => void>(() => {});
  const [caption, setCaption] = useState<{ index: number; text: string } | null>(null);
  // Latest values for the map's event handlers and the step animation.
  const insetsRef = useRef(insets);
  const selectRef = useRef(select);
  const reducedRef = useRef(reduced);
  useEffect(() => {
    insetsRef.current = insets;
    selectRef.current = select;
    reducedRef.current = reduced;
  });

  // Jump the timeline (and the historical basemap) to the battle's year.
  useEffect(() => {
    if (doc) setInstant(doc.year);
  }, [doc, setInstant]);

  // ── layers: add on a new story or a rebuilt style; remove on exit ──────────
  useEffect(() => {
    if (!map || !doc) return;
    registerStoryImages(map, storyPalette(doc));
    addStoryLayers(map);
    setEntityLayersVisible(map, false);
    setSourceData(map, STORY_SOURCES.terrain, terrainCollection(doc));
    setSourceData(map, STORY_SOURCES.mask, maskCollection(doc));
    setSourceData(map, STORY_SOURCES.alt, altSiteCollection(doc));
    // A rebuilt style lost the units; redraw what was on screen.
    const shown = shownRef.current;
    if (shown) {
      const stepDoc = doc.steps[shown.index];
      const stepFrames = phases[shown.index] ?? [];
      drawFrame(map, doc, shown.frame, stepDoc?.focus ?? []);
      setSourceData(map, STORY_SOURCES.moves, moveCollection(doc, stepDoc, stepFrames, shown.phase));
      setSourceData(map, STORY_SOURCES.notes, noteCollection(stepDoc, shown.phase));
      if (holds[shown.index]) setSourceData(map, STORY_SOURCES.hold, holdCollection(doc, holds[shown.index]));
      if (conditions[shown.index]) setLight(map, conditions[shown.index].light, false);
    }

    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12 });
    const onMove = (e: MapLayerMouseEvent) => {
      const id = e.features?.[0]?.properties?.id;
      const html = typeof id === 'string' ? unitCard(doc, id, shownRef.current?.frame.get(id)) : null;
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

    // Edge markers follow the camera (once per animation frame at most); the
    // wind/sun arrows turn against the map's bearing.
    let pending = 0;
    const place = () => {
      pending = 0;
      if (markersRef.current) {
        placeMarkers(map, markersRef.current, shownRef.current?.frame, unitInfo, tailsRef.current, insetsRef.current, reducedRef.current);
      }
      hudRef.current?.style.setProperty('--map-bearing', `${map.getBearing()}deg`);
    };
    const onCamera = () => {
      if (!pending) pending = requestAnimationFrame(place);
    };
    map.on('move', onCamera);
    placeRef.current = onCamera;
    place();

    return () => {
      for (const layer of STORY_INTERACTIVE_LAYERS) {
        map.off('mousemove', layer, onMove);
        map.off('mouseleave', layer, onLeave);
        map.off('click', layer, onClick);
      }
      map.off('move', onCamera);
      placeRef.current = () => {};
      cancelAnimationFrame(pending);
      popup.remove();
      cancelAnimationFrame(rafRef.current);
      // The style may already be gone (unmount during teardown).
      if (map.style) {
        removeStoryLayers(map);
        setEntityLayersVisible(map, true);
      }
    };
  }, [map, doc, styleEpoch, phases, holds, conditions, unitInfo]);

  // Leaving the story forgets what was shown, so re-entering starts fresh.
  useEffect(() => {
    if (!doc) shownRef.current = null;
  }, [doc]);

  // ── step changes: frame the step and animate the units into place ─────────
  useEffect(() => {
    if (!map || !doc || frames.length === 0 || !map.getSource(STORY_SOURCES.units)) return;
    const target = frames[index];
    const stepDoc = doc.steps[index];
    const stepFrames = phases[index];
    const stepPh = stepPhases(stepDoc);
    const last = stepPh.length - 1;
    const focus = stepDoc?.focus ?? [];
    const shown = shownRef.current;
    const refresh = () => placeRef.current();

    const showPhase = (upto: number) => {
      setSourceData(map, STORY_SOURCES.moves, moveCollection(doc, stepDoc, stepFrames, upto));
      setSourceData(map, STORY_SOURCES.notes, noteCollection(stepDoc, upto));
      tailsRef.current = moveTails(doc, stepDoc, stepFrames, upto);
    };
    setSourceData(map, STORY_SOURCES.hold, holdCollection(doc, holds[index]));
    setLight(map, conditions[index].light, !reduced && shown != null);

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
    const forward = shown != null && index === shown.index + 1;
    if (!shown || reduced || shown.index === index) {
      showPhase(last);
      drawFrame(map, doc, target, focus);
      setMoveOpacity(map, 1);
      shownRef.current = { frame: target, index, phase: last };
      refresh();
      return;
    }

    // Forward: the step's own movement, then each beat with its caption.
    // A jump or a step back glides straight to the step's final frame.
    const segments = forward
      ? stepPh.map((ph, q) => ({
          play: tweener(q === 0 ? shown.frame : stepFrames[q - 1], stepFrames[q], ph.moves),
          ms: q === 0 ? STEP_MS : BEAT_MS,
          phase: q,
          caption: ph.label,
        }))
      : [{ play: tweener(shown.frame, target, []), ms: JUMP_MS, phase: last, caption: null }];
    let seg = 0;
    let start = performance.now();
    let linger = 0;
    showPhase(segments[0].phase);
    setMoveOpacity(map, forward ? 0 : 1);
    const tick = (now: number) => {
      const s = segments[seg];
      const t = Math.min(1, (now - start) / s.ms);
      const frame = s.play(ease(t));
      drawFrame(map, doc, frame, focus);
      if (forward && seg === 0) setMoveOpacity(map, Math.min(1, t * 3));
      shownRef.current = { frame, index, phase: s.phase };
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else if (seg + 1 < segments.length) {
        seg++;
        start = now;
        // A beat: its arrows and notes join the step's, under its caption.
        showPhase(segments[seg].phase);
        const text = segments[seg].caption;
        if (text) setCaption({ index, text });
        rafRef.current = requestAnimationFrame(tick);
      } else {
        refresh();
        if (segments.length > 1) linger = window.setTimeout(() => setCaption(null), CAPTION_LINGER_MS);
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(rafRef.current);
      clearTimeout(linger);
    };
  }, [map, doc, frames, phases, holds, conditions, index, reduced, styleEpoch]);

  if (!doc) return null;
  const i = insets ?? NO_INSETS;
  const shownCaption = caption?.index === index ? caption.text : null;
  return (
    <div className="pointer-events-none absolute inset-0 z-[5] overflow-hidden">
      <div ref={markersRef} className="absolute inset-0" />
      {shownCaption && (
        <div
          className="absolute flex justify-center px-4"
          style={{ top: `calc(${i.top * 100}% + 14px)`, left: `${i.left * 100}%`, right: `${i.right * 100}%` }}
        >
          <span
            key={shownCaption}
            className="rounded-full border bg-card/95 px-3.5 py-1.5 text-center text-[13px] font-semibold text-foreground shadow-md backdrop-blur motion-safe:animate-in motion-safe:fade-in"
          >
            {shownCaption}
          </span>
        </div>
      )}
      <div
        ref={hudRef}
        className="absolute"
        style={{ top: `calc(${i.top * 100}% + 12px)`, right: `calc(${i.right * 100}% + 12px)` }}
      >
        {conditions[index] && <Hud conditions={conditions[index]} />}
      </div>
    </div>
  );
}
