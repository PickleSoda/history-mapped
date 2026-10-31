import { Head, Link, router } from '@inertiajs/react';
import { Search, X } from 'lucide-react';
import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import AppLayout from '@/layouts/app-layout';
import type { StorySummary } from '@/lib/map-story-doc';
import { edit as editStory, index as storiesIndex } from '@/routes/map-stories';
import type { BreadcrumbItem } from '@/types';

type Paginated<T> = {
    data: T[];
    current_page: number;
    last_page: number;
    total: number;
    links: { url: string | null; label: string; active: boolean }[];
};

type Props = {
    stories: Paginated<StorySummary>;
    filters: { search: string; kind: string; edited: string };
    kinds: string[];
};

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Map stories', href: storiesIndex.url() },
];

const yearLabel = (y: number | null) =>
    y === null ? '' : y < 0 ? `${-y} BCE` : `${y}`;

export default function MapStoriesIndex({ stories, filters, kinds }: Props) {
    const [search, setSearch] = useState(filters.search);

    const go = (params: Partial<Props['filters']>) => {
        const query = { ...filters, ...params };

        router.get(
            storiesIndex.url(),
            Object.fromEntries(
                Object.entries(query).filter(([, v]) => v !== ''),
            ),
            { preserveState: true, preserveScroll: true },
        );
    };

    const active = filters.search || filters.kind || filters.edited;

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Map stories" />
            <div className="flex flex-col gap-4 p-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">
                        Map stories
                    </h1>
                    <p className="text-sm text-muted-foreground">
                        Step-by-step stories on the atlas map — battles, wars,
                        epidemics, trade routes. Start a new one from an
                        entity's page (“Add a map story”). Stories edited here
                        differ from their file until{' '}
                        <code>php artisan map-stories:export</code>.
                    </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                    <form
                        className="flex gap-2"
                        onSubmit={(e) => {
                            e.preventDefault();
                            go({ search });
                        }}
                    >
                        <Input
                            className="w-64"
                            placeholder="Search title or slug"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                        <Button
                            type="submit"
                            variant="outline"
                            size="icon"
                            title="Search"
                        >
                            <Search className="size-4" />
                        </Button>
                    </form>
                    <select
                        className="h-9 rounded-md border bg-background px-2 text-sm"
                        value={filters.kind}
                        onChange={(e) => go({ kind: e.target.value })}
                        aria-label="Kind"
                    >
                        <option value="">All kinds</option>
                        {kinds.map((k) => (
                            <option key={k} value={k}>
                                {k.replace(/_/g, ' ')}
                            </option>
                        ))}
                    </select>
                    <select
                        className="h-9 rounded-md border bg-background px-2 text-sm"
                        value={filters.edited}
                        onChange={(e) => go({ edited: e.target.value })}
                        aria-label="Edited"
                    >
                        <option value="">Edited or not</option>
                        <option value="1">Edited here (not exported)</option>
                        <option value="0">Same as the file</option>
                    </select>
                    {active && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                                setSearch('');
                                router.get(storiesIndex.url());
                            }}
                        >
                            <X className="size-4" /> Clear
                        </Button>
                    )}
                    <span className="ml-auto text-sm text-muted-foreground">
                        {stories.total} stories
                    </span>
                </div>

                <div className="overflow-x-auto rounded-lg border">
                    <table className="w-full text-sm">
                        <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
                            <tr>
                                <th className="px-3 py-2">Story</th>
                                <th className="px-3 py-2">Kind</th>
                                <th className="px-3 py-2">Year</th>
                                <th className="px-3 py-2">Steps</th>
                                <th className="px-3 py-2">Belongs to</th>
                                <th className="px-3 py-2">State</th>
                            </tr>
                        </thead>
                        <tbody>
                            {stories.data.map((s) => (
                                <tr
                                    key={s.id}
                                    className="border-t hover:bg-muted/30"
                                >
                                    <td className="px-3 py-2">
                                        <Link
                                            href={editStory.url(s.slug)}
                                            className="font-medium hover:underline"
                                        >
                                            {s.title}
                                        </Link>
                                        <div className="font-mono text-xs text-muted-foreground">
                                            {s.slug}
                                        </div>
                                    </td>
                                    <td className="px-3 py-2">
                                        {s.kind.replace(/_/g, ' ')}
                                        {s.ambient && (
                                            <Badge
                                                variant="outline"
                                                className="ml-1"
                                            >
                                                ambient
                                            </Badge>
                                        )}
                                    </td>
                                    <td className="px-3 py-2">
                                        {yearLabel(s.year)}
                                    </td>
                                    <td className="px-3 py-2">
                                        {s.step_count}
                                    </td>
                                    <td className="px-3 py-2">
                                        {s.entity && (
                                            <Link
                                                href={`/entities/${s.entity.id}/edit`}
                                                className="hover:underline"
                                            >
                                                {s.entity.name}
                                            </Link>
                                        )}
                                        {s.chronicle && (
                                            <div className="text-xs text-muted-foreground">
                                                chronicle: {s.chronicle.title}
                                            </div>
                                        )}
                                    </td>
                                    <td className="px-3 py-2">
                                        {s.edited ? (
                                            <Badge
                                                className="bg-amber-100 text-amber-900 dark:bg-amber-900 dark:text-amber-100"
                                                title={s.edited_at ?? ''}
                                            >
                                                edited
                                                {s.edited_by
                                                    ? ` by ${s.edited_by}`
                                                    : ''}
                                            </Badge>
                                        ) : s.source_path ? (
                                            <span className="text-xs text-muted-foreground">
                                                as its file
                                            </span>
                                        ) : (
                                            <span className="text-xs text-muted-foreground">
                                                admin only
                                            </span>
                                        )}
                                    </td>
                                </tr>
                            ))}
                            {stories.data.length === 0 && (
                                <tr>
                                    <td
                                        colSpan={6}
                                        className="px-3 py-8 text-center text-muted-foreground"
                                    >
                                        No map stories match.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>

                {stories.last_page > 1 && (
                    <div className="flex flex-wrap gap-1">
                        {stories.links.map((l, i) =>
                            l.url ? (
                                <Link
                                    key={i}
                                    href={l.url}
                                    preserveScroll
                                    className={`rounded border px-2 py-1 text-xs ${l.active ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}
                                    dangerouslySetInnerHTML={{
                                        __html: l.label,
                                    }}
                                />
                            ) : (
                                <span
                                    key={i}
                                    className="rounded border px-2 py-1 text-xs opacity-40"
                                    dangerouslySetInnerHTML={{
                                        __html: l.label,
                                    }}
                                />
                            ),
                        )}
                    </div>
                )}
            </div>
        </AppLayout>
    );
}
