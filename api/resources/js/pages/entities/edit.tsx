import { Head, router } from '@inertiajs/react';
import { lazy, Suspense, useState } from 'react';
import EntityForm, { defaultFormData } from '@/components/entity-form';
import type { EntityFormData } from '@/components/entity-form';
import EntityGeoRefEditor from '@/components/entity-geo-ref-editor';
import EntityGeometryPeriodsPanel from '@/components/entity-geometry-periods-panel';
import HistoricalMapViewer from '@/components/historical-map-viewer';
import { Button } from '@/components/ui/button';
import AppLayout from '@/layouts/app-layout';
import type { GeoJsonLike } from '@/lib/geojson';
import { yearToOhmDate } from '@/lib/ohm-date';
import { update } from '@/routes/entities';
import * as RelationshipRoutes from '@/routes/entities/relationships';
import type { BreadcrumbItem, EntityDetail, EntityFormOptions } from '@/types';

const MapEditor = lazy(() => import('@/components/map-editor'));
const RelationshipPanel = lazy(() => import('@/components/relationship-panel'));

type Props = {
    entity: EntityDetail;
    formOptions: EntityFormOptions;
};

/** Populate EntityFormData from an existing EntityDetail for the edit form. */
function entityToFormData(entity: EntityDetail): EntityFormData {
    const base = defaultFormData();

    // Unpack attributes JSONB back into attr_* flat fields
    const attrFields: Record<string, string> = {};

    if (entity.attributes && typeof entity.attributes === 'object') {
        for (const [key, value] of Object.entries(entity.attributes)) {
            if (value !== null && value !== undefined) {
                attrFields[`attr_${key}`] = String(value);
            }
        }
    }

    return {
        ...base,
        name: entity.name ?? '',
        entity_type: entity.entity_type ?? '',
        entity_group: entity.entity_group ?? '',
        summary: entity.summary ?? '',
        significance: entity.significance ?? '',
        temporal_start: entity.temporal_start ?? '',
        temporal_end: entity.temporal_end ?? '',
        date_raw: entity.date_raw ?? '',
        date_method: entity.date_method ?? '',
        date_confidence: entity.date_confidence ?? '',
        duration_type: entity.duration_type ?? '',
        location_name: entity.location_name ?? '',
        location_confidence: entity.location_confidence ?? '',
        location_method: entity.location_method ?? '',
        impact_score:
            entity.impact_score != null ? String(entity.impact_score) : '',
        wikidata_id: entity.wikidata_id ?? '',
        tags: Array.isArray(entity.tags) ? entity.tags.join(', ') : '',
        alternative_names: Array.isArray(entity.alternative_names)
            ? entity.alternative_names.join(', ')
            : '',
        verification_status: entity.verification_status ?? 'pipeline_draft',
        confidence: entity.confidence ?? '',
        confidence_notes: entity.confidence_notes ?? '',
        display_priority:
            entity.display_priority != null
                ? String(entity.display_priority)
                : '',
        icon_class: entity.icon_class ?? '',
        entity_color: entity.entity_color ?? '',
        ...attrFields,
    };
}

export default function EntityEdit({ entity, formOptions }: Props) {
    const breadcrumbs: BreadcrumbItem[] = [
        { title: 'Dashboard', href: '/dashboard' },
        { title: 'Entities', href: '/entities' },
        { title: entity.name, href: `/entities/${entity.id}` },
        { title: 'Edit', href: `/entities/${entity.id}/edit` },
    ];

    const [data, setData] = useState<EntityFormData>(entityToFormData(entity));
    const [errors, setErrors] = useState<
        Partial<Record<keyof EntityFormData, string>>
    >({});
    const [processing, setProcessing] = useState(false);

    // Geometry state managed outside useForm (GeoJSON objects, not strings)
    const [geojson, setGeojson] = useState<GeoJsonLike>(entity.geojson ?? null);
    const [territoryGeojson, setTerritoryGeojson] = useState<GeoJsonLike>(
        entity.territory_geojson ?? null,
    );
    const [highlightedPeriodGeometries, setHighlightedPeriodGeometries] =
        useState<GeoJsonLike[]>([]);
    const [mapOpen, setMapOpen] = useState(false);
    const [geometryPeriodsOpen, setGeometryPeriodsOpen] = useState(false);
    const [relationshipOpen, setRelationshipOpen] = useState(false);
    const entityStartYear = Number(entity.temporal_start);
    const timeframeDate = Number.isFinite(entityStartYear)
        ? yearToOhmDate(entityStartYear)
        : null;

    function handleChange<K extends keyof EntityFormData>(
        field: K,
        value: EntityFormData[K],
    ) {
        setData((prev) => ({ ...prev, [field]: value }));
    }

    function handleSubmit(e: React.FormEvent) {
        e.preventDefault();

        // Collect attr_* keys into attributes object
        const attrEntries = Object.entries(data).filter(([key]) =>
            key.startsWith('attr_'),
        );
        const attributes: Record<string, unknown> = {};

        for (const [key, value] of attrEntries) {
            if (typeof value === 'string' && value.trim() !== '') {
                attributes[key.replace(/^attr_/, '')] = value;
            }
        }

        const payload: Record<string, any> = {};

        for (const [key, value] of Object.entries(data)) {
            if (!key.startsWith('attr_')) {
                payload[key] = value;
            }
        }

        payload['tags'] = data.tags
            ? data.tags
                  .split(',')
                  .map((s) => s.trim())
                  .filter(Boolean)
            : [];
        payload['alternative_names'] = data.alternative_names
            ? data.alternative_names
                  .split(',')
                  .map((s) => s.trim())
                  .filter(Boolean)
            : [];
        payload['attributes'] =
            Object.keys(attributes).length > 0 ? attributes : undefined;
        payload['geojson'] = geojson ?? undefined;
        payload['territory_geojson'] = territoryGeojson ?? undefined;

        setProcessing(true);
        router.put(update(entity.id), payload, {
            onError: (errs) =>
                setErrors(
                    errs as Partial<Record<keyof EntityFormData, string>>,
                ),
            onFinish: () => setProcessing(false),
        });
    }

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title={`Edit — ${entity.name}`} />

            <div className="mx-auto max-w-3xl p-4">
                <div className="mb-6">
                    <h1 className="text-2xl font-bold tracking-tight">
                        Edit Entity
                    </h1>
                    <p className="mt-1 text-sm text-muted-foreground">
                        {entity.name}
                    </p>
                </div>

                <EntityForm
                    data={data}
                    errors={errors}
                    processing={processing}
                    options={formOptions}
                    onChange={handleChange}
                    onSubmit={handleSubmit}
                    submitLabel="Save Changes"
                    onCancel={() => window.history.back()}
                />

                {/* Map editor — collapsible */}
                <div className="mt-6 rounded-lg border">
                    <button
                        type="button"
                        onClick={() => setMapOpen((v) => !v)}
                        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium"
                    >
                        <span>Map Editor</span>
                        <span className="text-xs text-muted-foreground">
                            {mapOpen ? 'Collapse' : 'Expand'}
                            {(geojson || territoryGeojson) && (
                                <span className="ml-2 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
                                    Geometry set
                                </span>
                            )}
                        </span>
                    </button>

                    {mapOpen && (
                        <div className="border-t">
                            <div className="border-b p-4">
                                <EntityGeoRefEditor
                                    entityId={entity.id}
                                    onHydratedGeometryChange={(geo, territory) => {
                                        setGeojson(geo);
                                        setTerritoryGeojson(territory);
                                    }}
                                />
                            </div>

                            <div className="border-b">
                                <div className="px-4 py-2">
                                    <p className="text-xs font-medium">
                                        Live Preview
                                    </p>
                                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                                        Uses the same viewer pipeline as the
                                        entity detail map.
                                    </p>
                                </div>
                                <HistoricalMapViewer
                                    baseGeometries={[geojson, territoryGeojson]}
                                    overlayGeometries={highlightedPeriodGeometries}
                                    timeframeDate={timeframeDate}
                                    fitBounds
                                />
                            </div>

                            <Suspense
                                fallback={
                                    <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
                                        Loading map…
                                    </div>
                                }
                            >
                                <MapEditor
                                    geojson={geojson}
                                    territoryGeojson={territoryGeojson}
                                    timeframeDate={timeframeDate}
                                    onChange={(geo, territory) => {
                                        setGeojson(geo);
                                        setTerritoryGeojson(territory);
                                    }}
                                />
                            </Suspense>
                            <div className="flex justify-end gap-2 border-t px-4 py-3">
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() => {
                                        setGeojson(null);
                                        setTerritoryGeojson(null);
                                    }}
                                >
                                    Clear geometry
                                </Button>
                                <Button
                                    type="button"
                                    size="sm"
                                    onClick={
                                        handleSubmit as unknown as React.MouseEventHandler
                                    }
                                    disabled={processing}
                                >
                                    Save with geometry
                                </Button>
                            </div>
                        </div>
                    )}
                </div>

                {/* Geometry periods — collapsible */}
                <div className="mt-4 rounded-lg border">
                    <button
                        type="button"
                        onClick={() => setGeometryPeriodsOpen((v) => !v)}
                        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium"
                    >
                        <span>Geometry Periods</span>
                        <span className="text-xs text-muted-foreground">
                            {geometryPeriodsOpen ? 'Collapse' : 'Expand'}
                        </span>
                    </button>

                    {geometryPeriodsOpen && (
                        <div className="border-t p-4">
                            <EntityGeometryPeriodsPanel
                                listUrl={entity.geometry_periods_url ?? `/entities/${entity.id}/geometry-periods`}
                                storeUrl={`/entities/${entity.id}/geometry-periods`}
                                updateUrlFn={(periodId) =>
                                    `/entities/${entity.id}/geometry-periods/${periodId}`
                                }
                                deleteUrlFn={(periodId) =>
                                    `/entities/${entity.id}/geometry-periods/${periodId}`
                                }
                                onSelectPeriod={(period) => {
                                    setHighlightedPeriodGeometries(
                                        period
                                            ? [period.geom ?? null, period.territory_geom ?? null]
                                            : [],
                                    );

                                    if (period) {
                                        setMapOpen(true);
                                    }
                                }}
                            />
                        </div>
                    )}
                </div>

                {/* Relationship panel — collapsible */}
                <div className="mt-4 rounded-lg border">
                    <button
                        type="button"
                        onClick={() => setRelationshipOpen((v) => !v)}
                        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium"
                    >
                        <span>Relationships</span>
                        <span className="text-xs text-muted-foreground">
                            {relationshipOpen ? 'Collapse' : 'Expand'}
                        </span>
                    </button>

                    {relationshipOpen && (
                        <div className="border-t p-4">
                            <Suspense
                                fallback={
                                    <div className="flex h-24 items-center justify-center text-sm text-muted-foreground">
                                        Loading relationships…
                                    </div>
                                }
                            >
                                <RelationshipPanel
                                    entityId={entity.id}
                                    listUrl={RelationshipRoutes.index.url(
                                        entity.id,
                                    )}
                                    storeUrl={RelationshipRoutes.store.url(
                                        entity.id,
                                    )}
                                    updateUrlFn={(relationshipId) =>
                                        `/entities/${entity.id}/relationships/${relationshipId}`
                                    }
                                    deleteUrlFn={(relationshipId) =>
                                        RelationshipRoutes.destroy.url({
                                            entity: entity.id,
                                            relationship: relationshipId,
                                        })
                                    }
                                />
                            </Suspense>
                        </div>
                    )}
                </div>
            </div>
        </AppLayout>
    );
}
