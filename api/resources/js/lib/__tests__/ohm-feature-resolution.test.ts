import { describe, expect, it } from 'vitest';
import {
    buildResolveOhmFeaturePayload,
    buildResolvedOhmSelectionFeature,
} from '../ohm-feature-resolution';

describe('ohm-feature-resolution', () => {
    it('builds a resolve payload from @id and timeframe dates', () => {
        const payload = buildResolveOhmFeaturePayload(
            {
                properties: {
                    '@id': 'relation/1880',
                },
            },
            {
                timeframeStartDate: '0100-01-01',
                timeframeEndDate: '0117-12-31',
                timeframeDate: null,
            },
        );

        expect(payload).toEqual({
            provider: 'ohm',
            external_type: 'relation',
            external_id: '1880',
            target_year: 100,
        });
    });

    it('falls back to osm_type and osm_id properties when @id is missing', () => {
        const payload = buildResolveOhmFeaturePayload(
            {
                properties: {
                    osm_type: 'way',
                    osm_id: 42,
                },
            },
            {
                timeframeDate: '0125',
                timeframeStartDate: null,
                timeframeEndDate: null,
            },
        );

        expect(payload).toEqual({
            provider: 'ohm',
            external_type: 'way',
            external_id: '42',
            target_year: 125,
        });
    });

    it('builds a synthetic selection feature from the clicked OHM geometry and resolved entity', () => {
        const feature = buildResolvedOhmSelectionFeature(
            {
                id: 'relation/1880',
                geometry: {
                    type: 'Polygon',
                    coordinates: [[[10, 40], [15, 40], [15, 45], [10, 45], [10, 40]]],
                },
                properties: {
                    name: 'Roman Empire',
                },
            },
            {
                entity: {
                    id: 'entity-1',
                    name: 'Roman Empire',
                    entity_type: 'political_entity',
                    entity_group: 'POLITY',
                },
                geo_ref_id: 'geo-ref-1',
                feature_ref: {
                    provider: 'ohm',
                    external_type: 'relation',
                    external_id: '1880',
                    geometry_period_id: null,
                    target_year: 117,
                },
                resolution_source: 'geometry_period',
                geometry: {
                    type: 'Point',
                    coordinates: [12.5, 41.9],
                },
            },
        );

        expect(feature).toMatchObject({
            id: 'relation/1880',
            geometry: {
                type: 'Polygon',
            },
            properties: {
                id: 'entity-1',
                name: 'Roman Empire',
                geo_ref_id: 'geo-ref-1',
                resolved_ohm_feature: true,
                external_type: 'relation',
                external_id: '1880',
            },
        });
    });
});