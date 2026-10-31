import { useQueryClient } from '@tanstack/react-query';
import type { GeoJSONSource, Map as MapLibreMap, MapLayerMouseEvent, MapMouseEvent } from 'maplibre-gl';
import maplibregl from 'maplibre-gl';
import { useEffect, useRef } from 'react';
import { create } from 'zustand';
import { STORY_INTERACTIVE_LAYERS } from '@/lib/map-story/layers';
import { adminOrigins, carryEntityIds, parseAdminMessage, PREVIEW, rejectedDocument, roundPoint } from '@/lib/map-story/preview';
import type { PreviewMessage } from '@/lib/map-story/preview';
import { qk } from '@/lib/query/queryKeys';
import type { LngLat, MapStory } from '@/lib/schemas/map-story';
import { useMapInstance } from './ephemeral';
import { useStoryNav } from './useStoryNav';

const ORIGINS = adminOrigins(import.meta.env.VITE_ADMIN_ORIGINS);
const PICK_SOURCE = 'story-preview-pick';

/** What the preview is picking for the admin, for the hint over the map. */
export const usePreviewPick = create<{ mode: 'point' | 'path' | null; points: number }>(() => ({ mode: null, points: 0 }));

/** Post to the admin page that embeds us (each allowed origin; the browser drops the rest). */
function post(message: PreviewMessage): void {
  if (window.parent === window) return;
  for (const origin of ORIGINS) window.parent.postMessage(message, origin);
}

function drawPick(map: MapLibreMap, path: LngLat[]): void {
  const data = {
    type: 'FeatureCollection' as const,
    features: [
      ...(path.length > 1 ? [{ type: 'Feature' as const, properties: {}, geometry: { type: 'LineString' as const, coordinates: path } }] : []),
      ...path.map((p) => ({ type: 'Feature' as const, properties: {}, geometry: { type: 'Point' as const, coordinates: p } })),
    ],
  };
  const source = map.getSource(PICK_SOURCE) as GeoJSONSource | undefined;
  if (source) {
    source.setData(data);
    return;
  }
  map.addSource(PICK_SOURCE, { type: 'geojson', data });
  map.addLayer({ id: `${PICK_SOURCE}-line`, type: 'line', source: PICK_SOURCE, paint: { 'line-color': '#db2777', 'line-width': 3, 'line-dasharray': [2, 1] } });
  map.addLayer({ id: `${PICK_SOURCE}-dot`, type: 'circle', source: PICK_SOURCE, filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-radius': 5, 'circle-color': '#db2777', 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
}

function clearPick(map: MapLibreMap): void {
  for (const id of [`${PICK_SOURCE}-dot`, `${PICK_SOURCE}-line`]) if (map.getLayer(id)) map.removeLayer(id);
  if (map.getSource(PICK_SOURCE)) map.removeSource(PICK_SOURCE);
}

/**
 * The SPA's half of the admin preview (`?preview=1`; see lib/map-story/preview):
 * draws the admin's draft by putting it in the story's query cache (so the
 * overlay and the player need no other change), follows and reports the step,
 * picks points and paths on the map, and lets units be dragged — reporting the
 * new centre. Does nothing outside preview mode.
 */
export function useStoryPreviewBridge(): void {
  const qc = useQueryClient();
  const { map } = useMapInstance();
  const { story, step, goto } = useStoryNav();
  const stepRef = useRef(step);
  const gotoRef = useRef(goto);
  useEffect(() => {
    stepRef.current = step;
    gotoRef.current = goto;
  });

  // Report every step change (the admin's scrubber follows the player).
  useEffect(() => {
    if (PREVIEW && story) post({ type: 'map-story:step-changed', index: step });
  }, [story, step]);

  // Messages from the admin; picking on the map.
  useEffect(() => {
    if (!PREVIEW) return;
    let pick: { mode: 'point' | 'path'; path: LngLat[] } | null = null;
    const endPick = (message: PreviewMessage | null) => {
      if (!pick) return;
      pick = null;
      usePreviewPick.setState({ mode: null, points: 0 });
      if (map) {
        clearPick(map);
        map.getCanvas().style.cursor = '';
        map.doubleClickZoom.enable();
      }
      if (message) post(message);
    };
    const onClick = (e: MapMouseEvent) => {
      if (!pick) return;
      const at = roundPoint(e.lngLat);
      if (pick.mode === 'point') {
        endPick({ type: 'map-story:picked', at });
        return;
      }
      pick.path.push(at);
      usePreviewPick.setState({ points: pick.path.length });
      if (map) drawPick(map, pick.path);
    };
    const onDoubleClick = () => {
      if (pick?.mode === 'path' && pick.path.length >= 2) endPick({ type: 'map-story:picked', path: pick.path });
    };
    const onKey = (e: KeyboardEvent) => {
      if (!pick) return;
      if (e.key === 'Escape') endPick({ type: 'map-story:pick-cancelled' });
      if (e.key === 'Enter' && pick.mode === 'path' && pick.path.length >= 2) endPick({ type: 'map-story:picked', path: pick.path });
    };
    const onMessage = (e: MessageEvent) => {
      const message = parseAdminMessage(e.origin, e.data, ORIGINS);
      if (!message) {
        const issues = rejectedDocument(e.origin, e.data, ORIGINS);
        if (issues) post({ type: 'map-story:document-rejected', issues });
        return;
      }
      if (message.type === 'map-story:document') {
        const key = qk.mapStory(message.document.slug);
        void qc.cancelQueries({ queryKey: key });
        qc.setQueryData<MapStory>(key, (old) => {
          const document = carryEntityIds(message.document, old?.document);
          return {
            id: old?.id ?? message.document.slug,
            slug: message.document.slug,
            kind: document.kind,
            title: document.title,
            year: document.year,
            step_count: document.steps.length,
            entity_id: old?.entity_id ?? document.entity?.entity_id ?? null,
            chronicle_id: old?.chronicle_id ?? null,
            period: old?.period ?? null,
            ambient: document.ambient,
            document,
          };
        });
        if (stepRef.current >= message.document.steps.length) gotoRef.current(message.document.steps.length - 1);
      } else if (message.type === 'map-story:step') {
        gotoRef.current(message.index);
      } else if (message.type === 'map-story:get-camera') {
        if (map) {
          const c = map.getCenter();
          post({ type: 'map-story:camera', center: roundPoint(c), zoom: Math.round(map.getZoom() * 100) / 100, bearing: Math.round(map.getBearing()) });
        }
      } else if (message.type === 'map-story:pick') {
        endPick(null);
        pick = { mode: message.mode, path: [] };
        usePreviewPick.setState({ mode: message.mode, points: 0 });
        if (map) {
          map.getCanvas().style.cursor = 'crosshair';
          if (message.mode === 'path') map.doubleClickZoom.disable();
        }
      } else {
        endPick({ type: 'map-story:pick-cancelled' });
      }
    };
    window.addEventListener('message', onMessage);
    window.addEventListener('keydown', onKey);
    map?.on('click', onClick);
    map?.on('dblclick', onDoubleClick);
    post({ type: 'map-story:ready' });
    return () => {
      window.removeEventListener('message', onMessage);
      window.removeEventListener('keydown', onKey);
      map?.off('click', onClick);
      map?.off('dblclick', onDoubleClick);
      endPick(null);
    };
  }, [map, qc]);

  // Drag a unit to move it: its new centre goes to the admin on drop.
  useEffect(() => {
    if (!PREVIEW || !map) return;
    let dragging: { unit: string; marker: maplibregl.Marker } | null = null;
    const onDown = (e: MapLayerMouseEvent) => {
      const unit = e.features?.[0]?.properties?.id;
      if (typeof unit !== 'string' || usePreviewPick.getState().mode) return;
      e.preventDefault();
      map.dragPan.disable();
      const el = document.createElement('div');
      el.className = 'size-4 rounded-full border-2 border-white bg-pink-600 shadow-md';
      dragging = { unit, marker: new maplibregl.Marker({ element: el }).setLngLat(e.lngLat).addTo(map) };
      map.getCanvas().style.cursor = 'grabbing';
    };
    const onMove = (e: MapMouseEvent) => dragging?.marker.setLngLat(e.lngLat);
    const onUp = (e: MapMouseEvent) => {
      if (!dragging) return;
      const { unit, marker } = dragging;
      dragging = null;
      marker.remove();
      map.dragPan.enable();
      map.getCanvas().style.cursor = '';
      post({ type: 'map-story:unit-dragged', unit, step: stepRef.current, at: roundPoint(e.lngLat) });
    };
    const layers = STORY_INTERACTIVE_LAYERS;
    for (const layer of layers) map.on('mousedown', layer, onDown);
    map.on('mousemove', onMove);
    map.on('mouseup', onUp);
    return () => {
      for (const layer of layers) map.off('mousedown', layer, onDown);
      map.off('mousemove', onMove);
      map.off('mouseup', onUp);
      dragging?.marker.remove();
      map.dragPan.enable();
    };
  }, [map]);
}
