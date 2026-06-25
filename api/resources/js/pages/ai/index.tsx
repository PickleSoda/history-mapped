import { Head } from '@inertiajs/react';
import AppLayout from '@/layouts/app-layout';
import type { BreadcrumbItem } from '@/types';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Create with AI', href: '/ai' },
];

export default function AiIndex() {
    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Create with AI" />
        </AppLayout>
    );
}
