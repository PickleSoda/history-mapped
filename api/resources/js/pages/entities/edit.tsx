import { Head, router } from '@inertiajs/react';
import { lazy, Suspense, useState } from 'react';
import { update } from '@/routes/entities';
import EntityForm, { defaultFormData, type EntityFormData } from '@/components/entity-form';
import { Button } from '@/components/ui/button';
import AppLayout from '@/layouts/app-layout';
import type { BreadcrumbItem, EntityDetail, EntityFormOptions } from '@/types';

const MapEditor = lazy(() => import('@/components/map-editor'));

type GeoJsonGeometry = Record<string, unknown> | null;

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
        impact_score: entity.impact_score != null ? String(entity.impact_score) : '',
        wikidata_id: entity.wikidata_id ?? '',
        tags: Array.isArray(entity.tags) ? entity.tags.join(', ') : '',
        alternative_names: Array.isArray(entity.alternative_names) ? entity.alternative_names.join(', ') : '',
        verification_status: entity.verification_status ?? 'pipeline_draft',
        confidence: entity.confidence ?? '',
        confidence_notes: entity.confidence_notes ?? '',
        display_priority: entity.display_priority != null ? String(entity.display_priority) : '',
        icon_class: entity.icon_class ?? '',
        entity_color: entity.entity_color ?? '',
        parent_entity_id: entity.parent_entity_id ?? '',
        successor_entity_id: entity.successor_entity_id ?? '',
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
    const [errors, setErrors] = useState<Partial<Record<keyof EntityFormData, string>>>({});
    const [processing, setProcessing] = useState(false);

    // Geometry state managed outside useForm (GeoJSON objects, not strings)
    const [geojson, setGeojson] = useState<GeoJsonGeometry>(entity.geojson ?? null);
    const [territoryGeojson, setTerritoryGeojson] = useState<GeoJsonGeometry>(entity.territory_geojson ?? null);
    const [mapOpen, setMapOpen] = useState(false);

    function handleChange<K extends keyof EntityFormData>(field: K, value: EntityFormData[K]) {
        setData((prev) => ({ ...prev, [field]: value }));
    }

    function handleSubmit(e: React.FormEvent) {
        e.preventDefault();

        // Collect attr_* keys into attributes object
        const attrEntries = Object.entries(data).filter(([key]) => key.startsWith('attr_'));
        const attributes: Record<string, unknown> = {};
        for (const [key, value] of attrEntries) {
            if (typeof value === 'string' && value.trim() !== '') {
                attributes[key.replace(/^attr_/, '')] = value;
            }
        }

        const payload: Record<string, unknown> = {};
        for (const [key, value] of Object.entries(data)) {
            if (!key.startsWith('attr_')) {
                payload[key] = value;
            }
        }

        payload['tags'] = data.tags ? data.tags.split(',').map((s) => s.trim()).filter(Boolean) : [];
        payload['alternative_names'] = data.alternative_names
            ? data.alternative_names.split(',').map((s) => s.trim()).filter(Boolean)
            : [];
        payload['attributes'] = Object.keys(attributes).length > 0 ? attributes : undefined;
        payload['geojson'] = geojson ?? undefined;
        payload['territory_geojson'] = territoryGeojson ?? undefined;

        setProcessing(true);
        router.put(update(entity.id), payload, {
            onError: (errs) => setErrors(errs as Partial<Record<keyof EntityFormData, string>>),
            onFinish: () => setProcessing(false),
        });
    }

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title={`Edit — ${entity.name}`} />

            <div className="mx-auto max-w-3xl p-4">
                <div className="mb-6">
                    <h1 className="text-2xl font-bold tracking-tight">Edit Entity</h1>
                    <p className="text-muted-foreground mt-1 text-sm">{entity.name}</p>
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
                        <span className="text-muted-foreground text-xs">
                            {mapOpen ? 'Collapse' : 'Expand'}
                            {(geojson || territoryGeojson) && (
                                <span className="bg-primary/10 text-primary ml-2 rounded px-1.5 py-0.5 text-[10px] font-semibold">
                                    Geometry set
                                </span>
                            )}
                        </span>
                    </button>

                    {mapOpen && (
                        <div className="border-t">
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
                                    onClick={handleSubmit as unknown as React.MouseEventHandler}
                                    disabled={processing}
                                >
                                    Save with geometry
                                </Button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </AppLayout>
    );
}
