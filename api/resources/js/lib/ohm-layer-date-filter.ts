import type { FilterSpecification, Map as MapLibreMap } from 'maplibre-gl';
import { normalizeOhmDate } from '@/lib/ohm-date';

type DateRange = {
    startISODate: string;
    endISODate: string;
    startDecimalDate: number;
    endDecimalDate: number;
};

export type OhmDateFilterInput =
    | Date
    | string
    | null
    | {
          start?: Date | string | null;
          end?: Date | string | null;
      };

type ApplyOptions = {
    includeUndated?: boolean;
};

const originalLayerFilters = new WeakMap<
    MapLibreMap,
    Map<string, FilterSpecification | null>
>();

function getOriginalFilters(
    map: MapLibreMap,
): Map<string, FilterSpecification | null> {
    let filters = originalLayerFilters.get(map);

    if (!filters) {
        filters = new Map<string, FilterSpecification | null>();
        originalLayerFilters.set(map, filters);
    }

    for (const layer of map.getStyle().layers ?? []) {
        if (!('source-layer' in layer)) {
            continue;
        }

        if (!filters.has(layer.id)) {
            filters.set(
                layer.id,
                (map.getFilter(layer.id) as
                    | FilterSpecification
                    | null
                    | undefined) ?? null,
            );
        }
    }

    return filters;
}

function dateFromUTC(year: number, month: number, day: number): Date {
    const date = new Date(Date.UTC(year, month, day));
    date.setUTCFullYear(year);

    return date;
}

function dateRangeFromISODate(isoDate: string): DateRange | null {
    if (!isoDate || !/^-?\d{1,4}(?:-\d\d){0,2}$/.test(isoDate)) {
        return null;
    }

    const ymd = isoDate.split('-');
    const isBCE = ymd[0] === '';

    if (isBCE) {
        ymd.shift();
        ymd[0] = String(Number(ymd[0]) * -1);
    }

    const startYear = Number(ymd[0]);
    let endYear = Number(ymd[0]);

    let startMonth = 0;
    let endMonth = 0;

    if (ymd[1]) {
        startMonth = Number(ymd[1]) - 1;
        endMonth = Number(ymd[1]) - 1;
    } else {
        endYear += 1;
    }

    let startDay = 1;
    let endDay = 1;

    if (ymd[2]) {
        startDay = Number(ymd[2]);
        endDay = Number(ymd[2]);
    } else if (ymd[1]) {
        endMonth += 1;
    }

    const startDate = dateFromUTC(startYear, startMonth, startDay);
    const endDate = dateFromUTC(endYear, endMonth, endDay);

    if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
        return null;
    }

    return {
        startISODate: startDate.toISOString().split('T')[0]!,
        endISODate: endDate.toISOString().split('T')[0]!,
        startDecimalDate: toDecimalYear(startDate),
        endDecimalDate: toDecimalYear(endDate),
    };
}

function dateRangeFromDate(date: Date | string | null): DateRange | null {
    if (typeof date === 'string') {
        return dateRangeFromISODate(date);
    }

    if (date instanceof Date && !Number.isNaN(date.getTime())) {
        const isoDate = date.toISOString().split('T')[0]!;

        return {
            startISODate: isoDate,
            endISODate: isoDate,
            startDecimalDate: toDecimalYear(date),
            endDecimalDate: toDecimalYear(date),
        };
    }

    return null;
}

function toDecimalYear(date: Date): number {
    const year = date.getUTCFullYear();
    const startOfYear = Date.UTC(year, 0, 1);
    const startOfNextYear = Date.UTC(year + 1, 0, 1);
    const elapsedMs = date.getTime() - startOfYear;
    const yearLengthMs = startOfNextYear - startOfYear;

    if (yearLengthMs <= 0) {
        return year;
    }

    return year + elapsedMs / yearLengthMs;
}

function normalizeDateInput(
    value: Date | string | null | undefined,
): Date | string | null {
    if (typeof value === 'string') {
        return normalizeOhmDate(value);
    }

    if (value instanceof Date) {
        return value;
    }

    return null;
}

function dateRangeFromInput(input: OhmDateFilterInput): DateRange | null {
    if (input && typeof input === 'object' && !(input instanceof Date)) {
        const rangeInput = input as {
            start?: Date | string | null;
            end?: Date | string | null;
        };
        const startRange = dateRangeFromDate(
            normalizeDateInput(rangeInput.start),
        );
        const endRange = dateRangeFromDate(normalizeDateInput(rangeInput.end));

        if (startRange && endRange) {
            return {
                startISODate: startRange.startISODate,
                endISODate: endRange.endISODate,
                startDecimalDate: startRange.startDecimalDate,
                endDecimalDate: endRange.endDecimalDate,
            };
        }

        return startRange ?? endRange ?? null;
    }

    return dateRangeFromDate(normalizeDateInput(input));
}

function isLegacyFilter(filter: unknown): boolean {
    if (!Array.isArray(filter) || filter.length < 2) {
        return false;
    }

    const args = filter.slice(1);

    switch (filter[0]) {
        case '!has':
        case '!in':
        case 'none':
            return true;
        case 'has':
            return args[0] === '$id' || args[0] === '$type';
        case 'in':
            return (
                args.length > 2 ||
                args[0] === '$id' ||
                args[0] === '$type' ||
                typeof args[1] === 'number' ||
                typeof args[1] === 'boolean' ||
                (typeof args[0] === 'string' && typeof args[1] === 'string')
            );
        case '==':
        case '!=':
        case '>':
        case '>=':
        case '<':
        case '<=':
            return typeof args[0] === 'string' && !Array.isArray(args[1]);
        case 'all':
        case 'any':
            return args.some(isLegacyFilter);
        default:
            return false;
    }
}

function buildLegacyDateFilter(
    dateRange: DateRange,
    originalFilter: FilterSpecification | null,
    includeUndated: boolean,
): FilterSpecification {
    const dateFilter: unknown[] = [
        'all',
        [
            'any',
            [
                'all',
                ['has', 'start_date'],
                ['<', 'start_date', dateRange.endISODate],
            ],
            ['all', ['!has', 'start_date']],
        ],
        [
            'any',
            [
                'all',
                ['has', 'end_date'],
                ['>=', 'end_date', dateRange.startISODate],
            ],
            ['all', ['!has', 'end_date']],
        ],
    ];

    if (!includeUndated) {
        dateFilter.splice(1, 0, [
            'any',
            ['has', 'start_date'],
            ['has', 'end_date'],
        ]);
    }

    if (originalFilter) {
        dateFilter.push(originalFilter);
    }

    return dateFilter as FilterSpecification;
}

function buildExpressionDateFilter(
    dateRange: DateRange,
    originalFilter: FilterSpecification | null,
    includeUndated: boolean,
): FilterSpecification {
    const startDec = dateRange.startDecimalDate;
    const endDec = dateRange.endDecimalDate;

    const dateFilter: unknown[] = [
        'all',
        [
            'any',
            [
                'all',
                ['has', 'start_decdate'],
                ['<', ['to-number', ['get', 'start_decdate']], endDec],
            ],
            [
                'all',
                ['!', ['has', 'start_decdate']],
                ['has', 'start_date'],
                ['<', ['get', 'start_date'], dateRange.endISODate],
            ],
            ['all', ['!', ['has', 'start_date']]],
        ],
        [
            'any',
            [
                'all',
                ['has', 'end_decdate'],
                ['>=', ['to-number', ['get', 'end_decdate']], startDec],
            ],
            [
                'all',
                ['!', ['has', 'end_decdate']],
                ['has', 'end_date'],
                ['>=', ['get', 'end_date'], dateRange.startISODate],
            ],
            ['all', ['!', ['has', 'end_date']]],
        ],
    ];

    if (!includeUndated) {
        dateFilter.splice(1, 0, [
            'any',
            ['has', 'start_date'],
            ['has', 'end_date'],
        ]);
    }

    if (originalFilter) {
        dateFilter.push(originalFilter);
    }

    return dateFilter as FilterSpecification;
}

export function applyOhmLayerDateFilter(
    map: MapLibreMap,
    date: OhmDateFilterInput,
    options?: ApplyOptions,
): void {
    const includeUndated = options?.includeUndated ?? false;
    const dateRange = dateRangeFromInput(date);
    const filters = getOriginalFilters(map);

    for (const layer of map.getStyle().layers ?? []) {
        if (!('source-layer' in layer)) {
            continue;
        }

        const originalFilter = filters.get(layer.id) ?? null;

        if (!dateRange) {
            map.setFilter(layer.id, originalFilter);
            continue;
        }

        const nextFilter = isLegacyFilter(originalFilter)
            ? buildLegacyDateFilter(dateRange, originalFilter, includeUndated)
            : buildExpressionDateFilter(
                  dateRange,
                  originalFilter,
                  includeUndated,
              );

        map.setFilter(layer.id, nextFilter);
    }
}
