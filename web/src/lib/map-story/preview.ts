/**
 * The admin's live preview of a map story (`?story=<slug>&sstep=<n>&preview=1`
 * inside an iframe in the admin editor). The admin and the SPA talk over
 * `postMessage`; this module is the protocol, free of React:
 *
 * admin → SPA
 *   {type: 'map-story:document', document}   draw this draft instead of the fetched story
 *   {type: 'map-story:step', index}          go to a step
 *   {type: 'map-story:pick', mode}           pick a point or a path on the map ('point' | 'path')
 *   {type: 'map-story:pick-cancel'}          stop picking
 *   {type: 'map-story:get-camera'}           report the current view
 * SPA → admin
 *   {type: 'map-story:ready'}
 *   {type: 'map-story:picked', at | path}    a picked point, or path (≥ 2 points)
 *   {type: 'map-story:pick-cancelled'}
 *   {type: 'map-story:unit-dragged', unit, step, at}
 *   {type: 'map-story:step-changed', index}
 *   {type: 'map-story:camera', center, zoom, bearing}       the answer to get-camera
 *   {type: 'map-story:document-rejected', issues}           a draft the story schema refused (the preview keeps the last good one)
 *
 * Only origins listed in VITE_ADMIN_ORIGINS (comma-separated; dev default
 * http://localhost:8000) are listened to, and every message is parsed with
 * zod — a draft document with the story schema — before it is used.
 */
import { z } from 'zod';
import { LngLatSchema, MapStoryDocumentSchema } from '@/lib/schemas/map-story';
import type { LngLat, MapStoryDocument } from '@/lib/schemas/map-story';

export const DEFAULT_ADMIN_ORIGINS = ['http://localhost:8000'];

/** Whether this page is the admin's preview (`?preview=1`). Read once: the flag never changes in a page's life. */
export const PREVIEW = typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('preview') === '1';

/** The admin origins allowed to drive the preview, from a comma-separated list. */
export function adminOrigins(list: string | undefined): string[] {
  const origins = (list ?? '')
    .split(',')
    .map((o) => o.trim().replace(/\/+$/, ''))
    .filter((o) => /^https?:\/\/[^/]+$/.test(o));
  return origins.length > 0 ? origins : DEFAULT_ADMIN_ORIGINS;
}

export function isAllowedOrigin(origin: string, allowed: readonly string[]): boolean {
  return allowed.includes(origin);
}

const AdminMessageSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('map-story:document'), document: MapStoryDocumentSchema }),
  z.object({ type: z.literal('map-story:step'), index: z.number().int().min(0) }),
  z.object({ type: z.literal('map-story:pick'), mode: z.enum(['point', 'path']) }),
  z.object({ type: z.literal('map-story:pick-cancel') }),
  z.object({ type: z.literal('map-story:get-camera') }),
]);
export type AdminMessage = z.infer<typeof AdminMessageSchema>;

/**
 * A message from the admin, or null when it is not one: from another origin,
 * of another shape, or carrying a document that does not parse.
 */
export function parseAdminMessage(origin: string, data: unknown, allowed: readonly string[]): AdminMessage | null {
  if (!isAllowedOrigin(origin, allowed)) return null;
  const parsed = AdminMessageSchema.safeParse(data);
  return parsed.success ? parsed.data : null;
}

type Json = unknown;
const isRecord = (v: Json): v is Record<string, Json> => typeof v === 'object' && v !== null && !Array.isArray(v);

/**
 * The schema's complaints about a draft from the admin (at most five, with
 * their paths), or null when the message is not a refused draft document.
 */
export function rejectedDocument(origin: string, data: unknown, allowed: readonly string[]): string[] | null {
  if (!isAllowedOrigin(origin, allowed) || !isRecord(data) || data.type !== 'map-story:document') return null;
  const parsed = MapStoryDocumentSchema.safeParse(data.document);
  if (parsed.success) return null;
  return parsed.error.issues.slice(0, 5).map((i) => `${i.path.join('.') || 'document'}: ${i.message}`);
}

export type PreviewMessage =
  | { type: 'map-story:ready' }
  | { type: 'map-story:picked'; at: LngLat }
  | { type: 'map-story:picked'; path: LngLat[] }
  | { type: 'map-story:pick-cancelled' }
  | { type: 'map-story:unit-dragged'; unit: string; step: number; at: LngLat }
  | { type: 'map-story:step-changed'; index: number }
  | { type: 'map-story:camera'; center: LngLat; zoom: number; bearing: number }
  | { type: 'map-story:document-rejected'; issues: string[] };

/** A point as the authoring tools write it: [lon, lat] to 5 decimals (about a metre). */
export function roundPoint(p: { lng: number; lat: number } | readonly [number, number]): LngLat {
  const [lng, lat] = 'lng' in p ? [p.lng, p.lat] : p;
  const r = (v: number) => Math.round(v * 1e5) / 1e5;
  return LngLatSchema.parse([r(lng), r(lat)]);
}

/**
 * The atlas ids a stored story resolved (`entity_id` beside each Q-id), put
 * back beside the same Q-ids in a draft: the admin edits the authored
 * document, which has none, and the preview needs them to draw `show`
 * entities and areas taken from entities, and to link names.
 */
export function carryEntityIds(draft: MapStoryDocument, stored: MapStoryDocument | undefined): MapStoryDocument {
  if (!stored) return draft;
  const ids = new Map<string, string>();
  const collect = (v: Json): void => {
    if (Array.isArray(v)) v.forEach(collect);
    else if (isRecord(v)) {
      if (typeof v.wikidata === 'string' && typeof v.entity_id === 'string') ids.set(v.wikidata, v.entity_id);
      Object.values(v).forEach(collect);
    }
  };
  collect(stored);
  if (ids.size === 0) return draft;
  const fill = (v: Json): Json => {
    if (Array.isArray(v)) return v.map(fill);
    if (!isRecord(v)) return v;
    const out: Record<string, Json> = {};
    for (const [k, item] of Object.entries(v)) out[k] = fill(item);
    if (typeof v.wikidata === 'string' && v.entity_id == null && ids.has(v.wikidata)) out.entity_id = ids.get(v.wikidata);
    return out;
  };
  return fill(draft) as MapStoryDocument;
}
