import type { MapLayerMouseEvent } from 'maplibre-gl';
import maplibregl from 'maplibre-gl';
import { useEffect, useMemo, useRef } from 'react';
import { storyKindLabel } from '@/components/atlas/StoryCard';
import { useChronicleNav, useMapInstance, useStoryNav, useStyleEpoch, useTimeState, useViewport } from '@/hooks';
import { useAmbientStories } from '@/hooks/useAmbientStories';
import { instantYear } from '@/lib/format';
import {
  addAmbientLayers,
  AMBIENT_INTERACTIVE_LAYERS,
  AMBIENT_SOURCE,
  ambientCollection,
  ENTITY_LAYERS,
  removeAmbientLayers,
  setAmbientVisible,
  setSourceData,
} from '@/lib/map-story/layers';

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);

/** The "Play" card for a clicked ambient feature, built as DOM (no React per click). */
function playCard(props: Record<string, unknown>, play: () => void): HTMLElement {
  const el = document.createElement('div');
  el.style.cssText = 'font:12px/1.4 system-ui,sans-serif;max-width:220px;display:grid;gap:4px';
  const kind = document.createElement('div');
  kind.style.cssText = 'color:#78716c;font-size:11px;text-transform:uppercase;letter-spacing:.04em';
  kind.textContent = storyKindLabel(String(props.kind ?? ''));
  const title = document.createElement('div');
  title.style.cssText = 'font-weight:600;font-size:13px';
  title.textContent = String(props.title ?? '');
  el.append(kind, title);
  if (props.step_title) {
    const step = document.createElement('div');
    step.style.color = '#57534e';
    step.textContent = String(props.step_title);
    el.append(step);
  }
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = '▶ Play';
  button.style.cssText =
    'margin-top:4px;justify-self:start;border-radius:8px;background:#b45309;color:#fff;font-weight:600;padding:4px 12px;cursor:pointer';
  button.onclick = play;
  el.append(button);
  return el;
}

/**
 * Stories that opt into ambient mode, drawn faintly on the plain atlas at the
 * timeline's year (their state at the last step started by then) under the
 * entity overlay. Hidden while a story or a chronicle plays. Hovering a feature
 * names its story; clicking one (off the entity overlay) opens a card whose
 * "Play" enters the story at that step.
 */
export function StoryAmbientLayer() {
  const { map } = useMapInstance();
  const { styleEpoch } = useStyleEpoch();
  const { isActive: storyActive, enter } = useStoryNav();
  const { isActive: chronicleActive } = useChronicleNav();
  const { time } = useTimeState();
  const { bbox } = useViewport();
  const hidden = storyActive || chronicleActive;
  const { data } = useAmbientStories(instantYear(time), bbox, !hidden);
  const collection = useMemo(() => ambientCollection(data ?? []), [data]);

  const enterRef = useRef(enter);
  useEffect(() => {
    enterRef.current = enter;
  });
  const cardRef = useRef<maplibregl.Popup | null>(null);
  const hoverRef = useRef<maplibregl.Popup | null>(null);

  // ── layers, under the entity overlay; re-added when the style is rebuilt ──
  useEffect(() => {
    if (!map) return;
    addAmbientLayers(map, ENTITY_LAYERS.find((id) => map.getLayer(id)));
    const hover = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 });
    hoverRef.current = hover;
    const onMove = (e: MapLayerMouseEvent) => {
      const p = e.features?.[0]?.properties;
      if (!p) return;
      map.getCanvas().style.cursor = 'pointer';
      const label = p.label && p.label !== p.title ? `<div style="color:#57534e">${esc(String(p.label))}</div>` : '';
      hover
        .setLngLat(e.lngLat)
        .setHTML(`<div style="font:12px/1.4 system-ui,sans-serif;max-width:220px"><b>${esc(String(p.title ?? ''))}</b>${label}</div>`)
        .addTo(map);
    };
    const onLeave = () => {
      map.getCanvas().style.cursor = '';
      hover.remove();
    };
    const onClick = (e: MapLayerMouseEvent) => {
      const p = e.features?.[0]?.properties;
      if (!p || typeof p.story !== 'string') return;
      // The entity overlay sits on top: a click on an entity is the entity's.
      const entityLayers = ENTITY_LAYERS.filter((id) => map.getLayer(id));
      if (entityLayers.length && map.queryRenderedFeatures(e.point, { layers: entityLayers }).length) return;
      // Claim the click, so the basemap doesn't also resolve it to an entity.
      e.preventDefault();
      hover.remove();
      cardRef.current?.remove();
      const slug = p.story;
      const step = typeof p.step === 'number' ? p.step : 0;
      const card = new maplibregl.Popup({ closeButton: true, closeOnClick: true, offset: 10, maxWidth: '240px' });
      card
        .setLngLat(e.lngLat)
        .setDOMContent(
          playCard(p, () => {
            card.remove();
            enterRef.current(slug, step);
          }),
        )
        .addTo(map);
      cardRef.current = card;
    };
    for (const layer of AMBIENT_INTERACTIVE_LAYERS) {
      map.on('mousemove', layer, onMove);
      map.on('mouseleave', layer, onLeave);
      map.on('click', layer, onClick);
    }
    return () => {
      for (const layer of AMBIENT_INTERACTIVE_LAYERS) {
        map.off('mousemove', layer, onMove);
        map.off('mouseleave', layer, onLeave);
        map.off('click', layer, onClick);
      }
      hover.remove();
      cardRef.current?.remove();
      if (map.style) removeAmbientLayers(map);
    };
  }, [map, styleEpoch]);

  // ── data, and hidden while a story or chronicle plays ──
  useEffect(() => {
    if (!map || !map.getSource(AMBIENT_SOURCE)) return;
    setSourceData(map, AMBIENT_SOURCE, collection);
  }, [map, collection, styleEpoch]);
  useEffect(() => {
    if (!map || !map.getSource(AMBIENT_SOURCE)) return;
    setAmbientVisible(map, !hidden);
    if (hidden) {
      cardRef.current?.remove();
      hoverRef.current?.remove();
    }
  }, [map, hidden, styleEpoch]);

  return null;
}
