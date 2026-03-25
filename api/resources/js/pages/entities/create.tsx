import type { FormDataConvertible } from '@inertiajs/core';
import { Head, router, useForm } from '@inertiajs/react';
import EntityForm, { defaultFormData } from '@/components/entity-form';
import type { EntityFormData } from '@/components/entity-form';
import AppLayout from '@/layouts/app-layout';
import { store } from '@/routes/entities';
import type { BreadcrumbItem, EntityFormOptions } from '@/types';

type Props = {
    formOptions: EntityFormOptions;
};

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Entities', href: '/entities' },
    { title: 'New Entity', href: '/entities/create' },
];

export default function EntityCreate({ formOptions }: Props) {
    const { data, setData, processing, errors } =
        useForm<EntityFormData>(defaultFormData());

    function handleChange<K extends keyof EntityFormData>(
        field: K,
        value: EntityFormData[K],
    ) {
        setData((previous) => ({
            ...previous,
            [field]: value,
        }));
    }

    function handleSubmit(e: React.FormEvent) {
        e.preventDefault();

        // Collect attr_* keys into attributes object, split comma strings to arrays
        const attrEntries = Object.entries(data).filter(([key]) =>
            key.startsWith('attr_'),
        );
        const attributes: Record<string, unknown> = {};

        for (const [key, value] of attrEntries) {
            if (typeof value === 'string' && value.trim() !== '') {
                attributes[key.replace(/^attr_/, '')] = value;
            }
        }

        const payload = {
            ...data,
            tags: data.tags
                ? data.tags
                      .split(',')
                      .map((s) => s.trim())
                      .filter(Boolean)
                : [],
            alternative_names: data.alternative_names
                ? data.alternative_names
                      .split(',')
                      .map((s) => s.trim())
                      .filter(Boolean)
                : [],
            attributes:
                Object.keys(attributes).length > 0 ? attributes : undefined,
        };

        // Strip attr_* keys — they are now in attributes
        for (const key of Object.keys(payload)) {
            if (key.startsWith('attr_')) {
                delete (payload as Record<string, unknown>)[key];
            }
        }

        router.post(
            store.url(),
            payload as unknown as Record<string, FormDataConvertible>,
        );
    }

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="New Entity" />

            <div className="mx-auto max-w-3xl p-4">
                <div className="mb-6">
                    <h1 className="text-2xl font-bold tracking-tight">
                        New Entity
                    </h1>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Fill in the fields below to create a new historical
                        entity.
                    </p>
                </div>

                <EntityForm
                    data={data}
                    errors={errors}
                    processing={processing}
                    options={formOptions}
                    onChange={handleChange}
                    onSubmit={handleSubmit}
                    submitLabel="Create Entity"
                    onCancel={() => window.history.back()}
                />
            </div>
        </AppLayout>
    );
}
