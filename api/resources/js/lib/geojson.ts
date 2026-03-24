export type GeoJsonLike = Record<string, unknown> | null;

export function normalizeToFeatures(value: GeoJsonLike): GeoJSON.Feature[] {
    if (!value || typeof value !== 'object') {
        return [];
    }

    const candidate = value as {
        type?: string;
        geometry?: GeoJSON.Geometry;
        features?: GeoJSON.Feature[];
        geometries?: GeoJSON.Geometry[];
    };

    if (
        candidate.type === 'FeatureCollection' &&
        Array.isArray(candidate.features)
    ) {
        return candidate.features.flatMap((feature) => {
            if (!feature.geometry) {
                return [];
            }

            return explodeGeometryToFeatures(
                feature.geometry,
                feature.properties ?? {},
            );
        });
    }

    if (candidate.type === 'Feature' && candidate.geometry) {
        return explodeGeometryToFeatures(
            candidate.geometry,
            (candidate as unknown as GeoJSON.Feature).properties ?? {},
        );
    }

    if (
        candidate.type === 'GeometryCollection' &&
        Array.isArray(candidate.geometries)
    ) {
        return candidate.geometries.flatMap((geometry) =>
            explodeGeometryToFeatures(geometry),
        );
    }

    if (candidate.type) {
        return explodeGeometryToFeatures(
            candidate as unknown as GeoJSON.Geometry,
        );
    }

    return [];
}

export function normalizeToFeatureCollection(
    values: GeoJsonLike[],
): GeoJSON.FeatureCollection {
    const features = values.flatMap((value) => normalizeToFeatures(value));

    return {
        type: 'FeatureCollection',
        features,
    };
}

function explodeGeometryToFeatures(
    geometry: GeoJSON.Geometry,
    properties: GeoJSON.GeoJsonProperties = {},
): GeoJSON.Feature[] {
    if (geometry.type === 'GeometryCollection') {
        return geometry.geometries.flatMap((child) =>
            explodeGeometryToFeatures(child, properties),
        );
    }

    return [{ type: 'Feature', geometry, properties }];
}

export function computeBoundsFromFeatures(
    features: GeoJSON.Feature[],
): [number, number, number, number] | null {
    let minLng = Number.POSITIVE_INFINITY;
    let minLat = Number.POSITIVE_INFINITY;
    let maxLng = Number.NEGATIVE_INFINITY;
    let maxLat = Number.NEGATIVE_INFINITY;

    for (const feature of features) {
        if (!feature.geometry) {
            continue;
        }

        const coordinates = extractCoordinatesFromGeometry(feature.geometry);

        for (const [lng, lat] of coordinates) {
            minLng = Math.min(minLng, lng);
            minLat = Math.min(minLat, lat);
            maxLng = Math.max(maxLng, lng);
            maxLat = Math.max(maxLat, lat);
        }
    }

    if (
        !Number.isFinite(minLng) ||
        !Number.isFinite(minLat) ||
        !Number.isFinite(maxLng) ||
        !Number.isFinite(maxLat)
    ) {
        return null;
    }

    return [minLng, minLat, maxLng, maxLat];
}

function extractCoordinates(value: unknown): number[][] {
    if (!Array.isArray(value)) {
        return [];
    }

    if (
        value.length >= 2 &&
        typeof value[0] === 'number' &&
        typeof value[1] === 'number'
    ) {
        return [[value[0], value[1]]];
    }

    const result: number[][] = [];

    for (const child of value) {
        result.push(...extractCoordinates(child));
    }

    return result;
}

function extractCoordinatesFromGeometry(
    geometry: GeoJSON.Geometry,
): number[][] {
    if (geometry.type === 'GeometryCollection') {
        const coordinates: number[][] = [];

        for (const child of geometry.geometries) {
            coordinates.push(...extractCoordinatesFromGeometry(child));
        }

        return coordinates;
    }

    return extractCoordinates(
        (geometry as Exclude<GeoJSON.Geometry, GeoJSON.GeometryCollection>)
            .coordinates as unknown,
    );
}
