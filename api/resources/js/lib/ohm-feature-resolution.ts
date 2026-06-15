type FeatureLike = {
    id?: string | number | null;
    geometry?: GeoJSON.Geometry | null;
    properties?: Record<string, unknown> | null;
};

type TimeframeInput = {
    timeframeDate?: string | null;
    timeframeStartDate?: string | null;
    timeframeEndDate?: string | null;
};

type OhmFeatureIdentity = {
    external_type: 'node' | 'way' | 'relation';
    external_id: string;
};

export type ResolveOhmFeaturePayload = {
    provider: 'ohm';
    external_type: 'node' | 'way' | 'relation';
    external_id: string;
    target_year: number;
};

export type ResolveOhmFeatureResponse = {
    entity: {
        id: string;
        name: string;
        entity_type: string | null;
        entity_group: string | null;
    };
    geo_ref_id: string;
    feature_ref: {
        provider: string | null;
        external_type: string | null;
        external_id: string;
        geometry_period_id: string | null;
        target_year: number;
    };
    resolution_source: string;
    geometry: Record<string, unknown>;
};

export function buildResolveOhmFeaturePayload(
    feature: FeatureLike,
    timeframe: TimeframeInput,
): ResolveOhmFeaturePayload | null {
    const identity = extractOhmFeatureIdentity(feature);
    const targetYear = extractTargetYear(timeframe);

    if (!identity || targetYear === null) {
        return null;
    }

    return {
        provider: 'ohm',
        external_type: identity.external_type,
        external_id: identity.external_id,
        target_year: targetYear,
    };
}

export function buildResolvedOhmSelectionFeature(
    feature: FeatureLike,
    resolution: ResolveOhmFeatureResponse,
): GeoJSON.Feature<GeoJSON.Geometry | null> {
    return {
        type: 'Feature',
        id:
            feature.id ??
            `${resolution.feature_ref.external_type ?? 'feature'}:${resolution.feature_ref.external_id}`,
        geometry: feature.geometry ?? null,
        properties: {
            ...(feature.properties ?? {}),
            id: resolution.entity.id,
            name:
                resolution.entity.name ??
                String(
                    feature.properties?.name ??
                        feature.properties?.label ??
                        'Entity',
                ),
            entity_type: resolution.entity.entity_type,
            entity_group: resolution.entity.entity_group,
            geo_ref_id: resolution.geo_ref_id,
            resolution_source: resolution.resolution_source,
            resolved_ohm_feature: true,
            external_type: resolution.feature_ref.external_type,
            external_id: resolution.feature_ref.external_id,
            target_year: resolution.feature_ref.target_year,
        },
    };
}

function extractOhmFeatureIdentity(
    feature: FeatureLike,
): OhmFeatureIdentity | null {
    const properties = feature.properties ?? {};
    const rawAtId = properties['@id'];

    if (typeof rawAtId === 'string' && rawAtId.trim() !== '') {
        const normalized = rawAtId.trim().toLowerCase();
        const slashMatch = normalized.match(/^(node|way|relation)\/(\d+)$/);

        if (slashMatch) {
            return {
                external_type:
                    slashMatch[1] as OhmFeatureIdentity['external_type'],
                external_id: slashMatch[2],
            };
        }

        const prefixMatch = normalized.match(/^([nwr])(\d+)$/);

        if (prefixMatch) {
            return {
                external_type: prefixToExternalType(prefixMatch[1]),
                external_id: prefixMatch[2],
            };
        }
    }

    const osmType =
        typeof properties.osm_type === 'string'
            ? properties.osm_type.toLowerCase()
            : null;
    const osmId = properties.osm_id;

    if (
        (osmType === 'node' || osmType === 'way' || osmType === 'relation') &&
        (typeof osmId === 'string' || typeof osmId === 'number')
    ) {
        return {
            external_type: osmType,
            external_id: String(osmId),
        };
    }

    return null;
}

function extractTargetYear(timeframe: TimeframeInput): number | null {
    return (
        parseYear(timeframe.timeframeStartDate ?? null) ??
        parseYear(timeframe.timeframeDate ?? null) ??
        parseYear(timeframe.timeframeEndDate ?? null)
    );
}

function parseYear(value: string | null): number | null {
    if (!value) {
        return null;
    }

    const match = value.trim().match(/^-?\d+/);

    if (!match) {
        return null;
    }

    const parsed = Number(match[0]);

    return Number.isFinite(parsed) ? parsed : null;
}

function prefixToExternalType(
    prefix: string,
): OhmFeatureIdentity['external_type'] {
    switch (prefix) {
        case 'n':
            return 'node';
        case 'w':
            return 'way';
        default:
            return 'relation';
    }
}
