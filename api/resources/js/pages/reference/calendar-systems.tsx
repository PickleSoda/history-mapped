import { Head } from '@inertiajs/react';
import { Badge } from '@/components/ui/badge';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table';
import { RefTableLayout } from '@/components/ref-table-layout';
import AppLayout from '@/layouts/app-layout';
import { index } from '@/routes/reference/calendar-systems';
import type { BreadcrumbItem, PaginatedData } from '@/types';
import type { CalendarSystem } from '@/types/reference';

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Reference', href: '#' },
    { title: 'Calendar Systems', href: index.url() },
];

type Filters = { search: string; per_page: number };

type Props = {
    calendars: PaginatedData<CalendarSystem>;
    filters: Filters;
};

export default function CalendarSystemsIndex({ calendars, filters }: Props) {
    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title="Calendar Systems" />

            <RefTableLayout
                title="Calendar Systems"
                description="Historical and modern calendar systems"
                basePath={index.url()}
                filters={filters}
                paginated={calendars}
            >
                <div className="overflow-hidden rounded-lg border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Name</TableHead>
                                <TableHead>Code</TableHead>
                                <TableHead>Type</TableHead>
                                <TableHead>Epoch (Gregorian)</TableHead>
                                <TableHead>Still in Use</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {calendars.data.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={5} className="h-24 text-center">
                                        <div className="text-muted-foreground">No records found.</div>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                calendars.data.map((calendar) => (
                                    <TableRow key={calendar.calendar_id}>
                                        <TableCell className="font-medium">{calendar.name}</TableCell>
                                        <TableCell className="font-mono text-sm">{calendar.code}</TableCell>
                                        <TableCell className="text-muted-foreground text-sm">
                                            {calendar.calendar_type}
                                        </TableCell>
                                        <TableCell className="text-muted-foreground tabular-nums text-sm">
                                            {calendar.epoch_gregorian ?? '—'}
                                        </TableCell>
                                        <TableCell>
                                            <Badge
                                                variant="outline"
                                                className={
                                                    calendar.still_in_use
                                                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                                        : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
                                                }
                                            >
                                                {calendar.still_in_use ? 'Yes' : 'No'}
                                            </Badge>
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </div>
            </RefTableLayout>
        </AppLayout>
    );
}
