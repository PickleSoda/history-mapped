import { Head, useForm } from '@inertiajs/react';
import { update } from '@/routes/entities';
import EntityForm, { defaultFormData, type EntityFormData } from '@/components/entity-form';
import AppLayout from '@/layouts/app-layout';
import type { BreadcrumbItem, EntityDetail, EntityFormOptions } from '@/types';

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

    const { data, setData, put, processing, errors } = useForm<EntityFormData>(
        entityToFormData(entity),
    );

    function handleChange<K extends keyof EntityFormData>(field: K, value: EntityFormData[K]) {
        setData(field, value);
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

        const payload = {
            ...data,
            tags: data.tags ? data.tags.split(',').map((s) => s.trim()).filter(Boolean) : [],
            alternative_names: data.alternative_names
                ? data.alternative_names.split(',').map((s) => s.trim()).filter(Boolean)
                : [],
            attributes: Object.keys(attributes).length > 0 ? attributes : undefined,
        };

        // Strip attr_* keys — they are now in attributes
        for (const key of Object.keys(payload)) {
            if (key.startsWith('attr_')) {
                delete (payload as Record<string, unknown>)[key];
            }
        }

        put(update(entity.id), { data: payload });
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
            </div>
        </AppLayout>
    );
}
