/**
 * Helpers for the admin's map-story editor: the authored document as plain
 * JSON (schema 1–3; see docs/implementation-docs/map-story-authoring.md),
 * where its parts live, renames that keep references intact, geometry to and
 * from GeoJSON for the map editor, and where a server message points.
 */

// The document is authored JSON: any shape the validator accepts.
export type StoryDoc = Record<string, any>;
export type LngLat = [number, number];

export type StoryVocabulary = {
    story_kinds: string[];
    battle_kinds: string[];
    military_kinds: string[];
    unit_kinds: string[];
    point_unit_kinds: string[];
    shapes: string[];
    unit_states: string[];
    move_types: string[];
    note_kinds: string[];
    feature_kinds: Record<string, 'at' | 'line' | 'area'>;
    feature_states: string[];
    route_kinds: string[];
    region_kinds: string[];
    legend_styles: string[];
    lights: string[];
    wind_strengths: string[];
    source_kinds: string[];
    max_beats: number;
    text_limits: Record<string, [number, number]>;
    route_colors: Record<string, string>;
    region_colors: Record<string, string>;
};

export type StorySummary = {
    id: string;
    slug: string;
    title: string;
    kind: string;
    year: number | null;
    step_count: number;
    ambient: boolean;
    entity: { id: string; name: string } | null;
    chronicle: { id: string; slug: string; title: string } | null;
    source_path: string | null;
    edited: boolean;
    edited_at: string | null;
    edited_by: string | null;
    synced_at: string | null;
    updated_at: string | null;
};

export type LinkedEntity = { id: string; name: string; type: string | null };

/** Deep copy (the document is plain JSON). */
export function clone<T>(value: T): T {
    return JSON.parse(JSON.stringify(value)) as T;
}

/** The document's feature list key: `features` (schema 3) or the older `terrain`. */
export function featuresKey(doc: StoryDoc): 'features' | 'terrain' {
    return 'terrain' in doc && !('features' in doc) ? 'terrain' : 'features';
}

/** A step's feature-state key: what it already uses, else what the story's era calls it. */
export function stepStateKey(
    doc: StoryDoc,
    step: StoryDoc,
): 'features' | 'terrain_state' {
    if ('features' in step) {
        return 'features';
    }

    if ('terrain_state' in step) {
        return 'terrain_state';
    }

    return featuresKey(doc) === 'terrain' || (doc.schema ?? 3) < 3
        ? 'terrain_state'
        : 'features';
}

export type IssueTarget = {
    tab: 'overview' | 'sides' | 'features' | 'steps';
    /** The step id, for a step's issue. */
    step?: string;
    /** The list index, for a side, unit or feature. */
    index?: number;
    /** `sides` or `units`, for that tab. */
    list?: 'sides' | 'units';
    /** A top-level field name, for the overview. */
    field?: string;
};

const OVERVIEW_FIELDS = [
    'schema',
    'slug',
    'kind',
    'entity',
    'chronicle',
    'title',
    'date_label',
    'year',
    'intro',
    'outcome',
    'uncertainty',
    'sources',
    'camera',
    'alt_sites',
    'period',
    'ambient',
    'legend',
];

/** Where an error or warning message (MapStoryDocument / MapStoryWarnings wording) points. */
export function issueTarget(message: string): IssueTarget {
    const step = /^step '([^']*)'/.exec(message);

    if (step) {
        return { tab: 'steps', step: step[1] };
    }

    const list = /^(units|sides)(?:\[(\d+)\])?/.exec(message);

    if (list) {
        return {
            tab: 'sides',
            list: list[1] as 'sides' | 'units',
            index: list[2] !== undefined ? Number(list[2]) : undefined,
        };
    }

    const feature = /^(features|terrain)\[(\d+)\]/.exec(message);

    if (feature) {
        return { tab: 'features', index: Number(feature[2]) };
    }

    const field = /^([a-z_]+)/.exec(message)?.[1];

    return {
        tab: 'overview',
        field: field && OVERVIEW_FIELDS.includes(field) ? field : undefined,
    };
}

/** The messages that point at one target (for showing them next to the field). */
export function issuesFor(
    messages: string[],
    match: (target: IssueTarget) => boolean,
): string[] {
    return messages.filter((m) => match(issueTarget(m)));
}

/** A free lowercase id: `base`, else `base-2`, `base-3`, … */
export function freeId(base: string, taken: Iterable<string>): string {
    const used = new Set(taken);
    const root =
        base
            .toLowerCase()
            .replace(/[^a-z0-9-]+/g, '-')
            .replace(/^-+|-+$/g, '')
            .slice(0, 56) || 'item';

    if (!used.has(root)) {
        return root;
    }

    for (let n = 2; ; n++) {
        if (!used.has(`${root}-${n}`)) {
            return `${root}-${n}`;
        }
    }
}

/** The step and each of its beats: each has positions, moves and notes. */
export function phasesOf(step: StoryDoc): StoryDoc[] {
    return [step, ...(Array.isArray(step.beats) ? step.beats : [])];
}

function renameKey(obj: StoryDoc | undefined, from: string, to: string): void {
    if (!obj || typeof obj !== 'object' || !(from in obj)) {
        return;
    }

    // Rebuild to keep the key's place in the order.
    const entries = Object.entries(obj).map(
        ([k, v]) => [k === from ? to : k, v] as const,
    );

    for (const k of Object.keys(obj)) {
        delete obj[k];
    }

    for (const [k, v] of entries) {
        obj[k] = v;
    }
}

/** Rename a unit and every reference to it (placements, arrows, focus, with/from/into, fire targets). */
export function renameUnit(doc: StoryDoc, from: string, to: string): StoryDoc {
    const next = clone(doc);

    for (const unit of next.units ?? []) {
        if (unit.id === from) {
            unit.id = to;
        }
    }

    for (const step of next.steps ?? []) {
        for (const phase of phasesOf(step)) {
            renameKey(phase.positions, from, to);

            for (const placement of Object.values(
                phase.positions ?? {},
            ) as StoryDoc[]) {
                for (const key of ['with', 'from', 'into']) {
                    if (placement?.[key] === from) {
                        placement[key] = to;
                    }
                }
            }

            for (const move of phase.moves ?? []) {
                if (move.unit === from) {
                    move.unit = to;
                }

                if (move.target === from) {
                    move.target = to;
                }
            }

            if (Array.isArray(phase.focus)) {
                phase.focus = phase.focus.map((u: string) =>
                    u === from ? to : u,
                );
            }
        }
    }

    return next;
}

/** Rename a side and every reference to it (units, holders, captors, colours of features, side arrows). */
export function renameSide(doc: StoryDoc, from: string, to: string): StoryDoc {
    const next = clone(doc);

    for (const side of next.sides ?? []) {
        if (side.id === from) {
            side.id = to;
        }
    }

    for (const unit of next.units ?? []) {
        if (unit.side === from) {
            unit.side = to;
        }
    }

    for (const feature of next[featuresKey(next)] ?? []) {
        if (feature.side === from) {
            feature.side = to;
        }
    }

    for (const step of next.steps ?? []) {
        for (const state of Object.values(
            step.features ?? step.terrain_state ?? {},
        ) as StoryDoc[]) {
            if (state?.held_by === from) {
                state.held_by = to;
            }
        }

        for (const phase of phasesOf(step)) {
            for (const placement of Object.values(
                phase.positions ?? {},
            ) as StoryDoc[]) {
                if (placement?.by === from) {
                    placement.by = to;
                }
            }

            for (const move of phase.moves ?? []) {
                if (move.side === from) {
                    move.side = to;
                }
            }
        }
    }

    return next;
}

/** Rename a feature and its per-step state keys. */
export function renameFeature(
    doc: StoryDoc,
    from: string,
    to: string,
): StoryDoc {
    const next = clone(doc);

    for (const feature of next[featuresKey(next)] ?? []) {
        if (feature.id === from) {
            feature.id = to;
        }
    }

    for (const step of next.steps ?? []) {
        renameKey(step.features, from, to);
        renameKey(step.terrain_state, from, to);
    }

    return next;
}

/**
 * Where a unit stands just before step `index` (its last `at` in an earlier
 * step or beat), or null when it has not been placed with a point yet.
 */
export function lastPosition(
    doc: StoryDoc,
    index: number,
    unit: string,
): LngLat | null {
    let at: LngLat | null = null;

    for (const step of (doc.steps ?? []).slice(0, index)) {
        for (const phase of phasesOf(step)) {
            const p = phase.positions?.[unit];

            if (Array.isArray(p?.at)) {
                at = p.at as LngLat;
            }
        }
    }

    return at;
}

/**
 * Put a unit at `at` in a step (from a drag in the preview, or a pick): its
 * placement there gets the point, and its arrow in that step (if any) now ends
 * there.
 */
export function moveUnitTo(
    doc: StoryDoc,
    index: number,
    unit: string,
    at: LngLat,
): StoryDoc {
    const next = clone(doc);
    const step = next.steps?.[index];

    if (!step) {
        return next;
    }

    step.positions = step.positions ?? {};
    const placement = { ...(step.positions[unit] ?? {}), at };
    delete placement.with;
    step.positions[unit] = placement;

    const move = [...(step.moves ?? [])]
        .reverse()
        .find((m: StoryDoc) => m.unit === unit && Array.isArray(m.path));

    if (move && move.type !== 'fire' && move.type !== 'blockade') {
        move.path[move.path.length - 1] = at;
    }

    return next;
}

// ── Geometry ↔ GeoJSON (the map editor speaks GeoJSON) ───────────────────────

type Geometry = Record<string, any> | null;

const isPoint = (v: unknown): v is LngLat =>
    Array.isArray(v) && typeof v[0] === 'number' && typeof v[1] === 'number';

const close = (ring: LngLat[]): LngLat[] =>
    ring.length > 0 ? [...ring, ring[0]!] : ring;

const open = (ring: LngLat[]): LngLat[] =>
    ring.length > 1 &&
    ring[0]![0] === ring[ring.length - 1]![0] &&
    ring[0]![1] === ring[ring.length - 1]![1]
        ? ring.slice(0, -1)
        : ring;

const round = (p: number[]): LngLat => [
    Math.round(p[0]! * 1e5) / 1e5,
    Math.round(p[1]! * 1e5) / 1e5,
];

/** A feature's `at` / `line` / `area` as GeoJSON for the map editor. */
export function toGeoJson(
    kind: 'at' | 'line' | 'area',
    value: unknown,
): Geometry {
    if (kind === 'at') {
        return isPoint(value) ? { type: 'Point', coordinates: value } : null;
    }

    if (kind === 'line') {
        return Array.isArray(value) && value.length >= 2
            ? { type: 'LineString', coordinates: value }
            : null;
    }

    if (!Array.isArray(value) || value.length === 0) {
        return null;
    }

    if (isPoint(value[0])) {
        return { type: 'Polygon', coordinates: [close(value as LngLat[])] };
    }

    return {
        type: 'MultiPolygon',
        coordinates: (value as LngLat[][]).map((ring) => [close(ring)]),
    };
}

/** The map editor's GeoJSON back as an `at`, a `line`, or an `area` (one ring, or a list of rings; holes dropped). */
export function fromGeoJson(
    kind: 'at' | 'line' | 'area',
    geo: Geometry,
): unknown {
    const geometries: Record<string, any>[] = !geo
        ? []
        : geo.type === 'FeatureCollection'
          ? (geo.features ?? []).map((f: any) => f.geometry).filter(Boolean)
          : geo.type === 'Feature'
            ? [geo.geometry]
            : [geo];

    if (kind === 'at') {
        const point = geometries.find((g) => g.type === 'Point');

        return point ? round(point.coordinates) : null;
    }

    if (kind === 'line') {
        const line = geometries.find((g) => g.type === 'LineString');

        return line ? line.coordinates.map(round) : null;
    }

    const rings: LngLat[][] = [];

    for (const g of geometries) {
        if (g.type === 'Polygon') {
            rings.push(open(g.coordinates[0].map(round)));
        } else if (g.type === 'MultiPolygon') {
            for (const polygon of g.coordinates) {
                rings.push(open(polygon[0].map(round)));
            }
        }
    }

    if (rings.length === 0) {
        return null;
    }

    return rings.length === 1 ? rings[0] : rings;
}

/** "N characters (aim for lo–hi)" status for a text against its limits. */
export function lengthStatus(
    text: unknown,
    limits: [number, number] | undefined,
): { n: number; ok: boolean; label: string } {
    const n = typeof text === 'string' ? text.trim().length : 0;

    if (!limits) {
        return { n, ok: true, label: `${n}` };
    }

    const [lo, hi] = limits;

    return { n, ok: n >= lo && n <= hi, label: `${n} / ${lo}–${hi}` };
}
