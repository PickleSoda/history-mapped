export type DiffRow = {
    label: string;
    from: string | null;
    to: string | null;
    kind: 'change' | 'create' | 'merge';
};

const MAX_LEN = 120;

function truncate(s: string): string {
    return s.length > MAX_LEN ? `${s.slice(0, MAX_LEN)}…` : s;
}

function isRecord(v: unknown): v is Record<string, unknown> {
    return typeof v === 'object' && v !== null && !Array.isArray(v);
}

/** Format any value into a short display string. Total — never throws. */
export function formatValue(v: unknown): string {
    if (v === null || v === undefined) {
        return '—';
    }

    if (typeof v === 'number' || typeof v === 'boolean') {
        return String(v);
    }

    if (typeof v === 'string') {
        return truncate(v);
    }

    if (Array.isArray(v)) {
        return truncate(v.map(formatValue).join(', '));
    }

    try {
        return truncate(JSON.stringify(v));
    } catch {
        return '—';
    }
}

function labelForTool(tool: string): string {
    if (tool === 'set_entity_wikidata') {
        return 'Wikidata QID';
    }

    if (tool === 'set_entity_location') {
        return 'Location';
    }

    if (!tool) {
        return 'Change';
    }

    const spaced = tool.replace(/_/g, ' ');

    return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/**
 * Flatten a stored `human_diff` (heterogeneous per tool) into uniform diff rows.
 * Total and defensive: unknown or malformed shapes return [] so the card falls
 * back to its summary line and a new backend tool can never break rendering.
 */
export function normalizeHumanDiff(
    tool: string,
    humanDiff: unknown,
): DiffRow[] {
    if (!isRecord(humanDiff)) {
        return [];
    }

    // 1) Field-level edits: { diff: { field: { from, to } } }
    const diff = humanDiff.diff;

    if (isRecord(diff)) {
        const rows: DiffRow[] = [];

        for (const [field, change] of Object.entries(diff)) {
            if (isRecord(change) && ('from' in change || 'to' in change)) {
                rows.push({
                    label: field,
                    from: formatValue(change.from),
                    to: formatValue(change.to),
                    kind: 'change',
                });
            }
        }

        if (rows.length > 0) {
            return rows;
        }
    }

    // 2) Create field-lists: { fields: {...} }
    const fields = humanDiff.fields;

    if (isRecord(fields)) {
        return Object.entries(fields).map(([field, value]) => ({
            label: field,
            from: null,
            to: formatValue(value),
            kind: 'create' as const,
        }));
    }

    // 3) Merge: { survivor_name, loser_name }
    if ('survivor_name' in humanDiff || 'loser_name' in humanDiff) {
        return [
            {
                label: 'merge',
                from: formatValue(humanDiff.loser_name),
                to: formatValue(humanDiff.survivor_name),
                kind: 'merge',
            },
        ];
    }

    // 4) Top-level from/to: Wikidata, location
    if ('from' in humanDiff || 'to' in humanDiff) {
        let to = formatValue(humanDiff.to);

        if (
            typeof humanDiff.verified_label === 'string' &&
            humanDiff.to != null
        ) {
            to = `${to} (${humanDiff.verified_label})`;
        }

        return [
            {
                label: labelForTool(tool),
                from: formatValue(humanDiff.from),
                to,
                kind: 'change',
            },
        ];
    }

    // 5) Summary-only / unrecognized
    return [];
}
