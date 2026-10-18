<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

use App\Support\ContentBundle\RecordType;

/**
 * The per-record rules, free of I/O so the import planner can run them on merged records too: year order,
 * text year against integer year, and the CHECK constraints the database enforces (gp_has_geometry,
 * gp_derived_requires_source, gp_presence_requires_relationship, el_has_locator).
 *
 * `$complete` says whether absent keys mean null. It is true for new-record and `replace` lines and for a
 * fully merged record. For a partial `merge` line pass false: a CHECK rule is then evaluated only when every
 * key it reads is present. Year rules only look at keys that are present. Nested `locations` are always
 * checked, since a present list replaces the whole list.
 */
final class RecordRules
{
    /**
     * Year pairs per type: [startYearKey, endYearKey, startTextKey|null, endTextKey|null].
     *
     * @return array{string, string, ?string, ?string}|null
     */
    private static function yearPair(RecordType $type): ?array
    {
        return match ($type) {
            RecordType::Relationships => ['start_year', 'end_year', 'temporal_start', 'temporal_end'],
            RecordType::GeoRefs => ['temporal_start_year', 'temporal_end_year', 'temporal_start', 'temporal_end'],
            RecordType::GeometryPeriods, RecordType::Chronicles, RecordType::ChronicleEntries => ['start_year', 'end_year', null, null],
            RecordType::Entities => null,
        };
    }

    /**
     * CHECK rules on geometry periods: keys read, predicate true when violated, pointer, message.
     *
     * @return list<array{keys: list<string>, violated: \Closure(\stdClass): bool, field: string, message: string}>
     */
    private static function geometryPeriodChecks(): array
    {
        return [
            [
                'keys' => ['geom', 'territory_geom'],
                'violated' => fn (\stdClass $d) => ($d->geom ?? null) === null && ($d->territory_geom ?? null) === null,
                'field' => '/geom',
                'message' => 'a geometry period needs `geom` or `territory_geom`',
            ],
            [
                'keys' => ['provenance_mode', 'relationship_id', 'source_event_id'],
                'violated' => fn (\stdClass $d) => ($d->provenance_mode ?? null) === 'derived' && ($d->relationship_id ?? null) === null && ($d->source_event_id ?? null) === null,
                'field' => '/provenance_mode',
                'message' => 'a derived geometry period needs `relationship_id` or `source_event_id`',
            ],
            [
                'keys' => ['period_type', 'relationship_id'],
                'violated' => fn (\stdClass $d) => ($d->period_type ?? null) === 'presence' && ($d->relationship_id ?? null) === null,
                'field' => '/relationship_id',
                'message' => 'a presence geometry period needs `relationship_id`',
            ],
        ];
    }

    /** @return list<RuleViolation> */
    public static function check(RecordType $type, \stdClass $record, bool $complete): array
    {
        $found = [];

        $pair = self::yearPair($type);
        if ($pair !== null) {
            self::years($record, '', $pair, $found);
        }
        if ($type === RecordType::Entities) {
            foreach (is_array($record->temporal_ranges ?? null) ? $record->temporal_ranges : [] as $i => $range) {
                if ($range instanceof \stdClass) {
                    self::years($range, "/temporal_ranges/{$i}", ['start_year', 'end_year', 'start_date', 'end_date'], $found);
                }
            }
            foreach (is_array($record->locations ?? null) ? $record->locations : [] as $i => $loc) {
                if ($loc instanceof \stdClass && ($loc->location_name ?? null) === null && ($loc->geom ?? null) === null && ($loc->territory_geom ?? null) === null) {
                    $found[] = new RuleViolation("/locations/{$i}", 'a location needs `location_name`, `geom` or `territory_geom`');
                }
            }
        }

        if ($type === RecordType::GeometryPeriods) {
            foreach (self::geometryPeriodChecks() as $rule) {
                $present = $complete || count(array_filter($rule['keys'], fn ($k) => property_exists($record, $k))) === count($rule['keys']);
                if ($present && ($rule['violated'])($record)) {
                    $found[] = new RuleViolation($rule['field'], $rule['message']);
                }
            }
        }

        return $found;
    }

    /**
     * @param  array{string, string, ?string, ?string}  $pair
     * @param  list<RuleViolation>  $found
     */
    private static function years(\stdClass $o, string $at, array $pair, array &$found): void
    {
        [$startKey, $endKey, $startText, $endText] = $pair;
        $start = isset($o->$startKey) && is_int($o->$startKey) ? $o->$startKey : null;
        $end = isset($o->$endKey) && is_int($o->$endKey) ? $o->$endKey : null;
        if ($start !== null && $end !== null && $start > $end) {
            $found[] = new RuleViolation("{$at}/{$startKey}", "`{$startKey}` {$start} is after `{$endKey}` {$end}");
        }

        foreach ([[$startText, $start, $startKey], [$endText, $end, $endKey]] as [$textKey, $year, $yearKey]) {
            if ($textKey === null || $year === null || ! isset($o->$textKey) || ! is_string($o->$textKey)) {
                continue;
            }
            if (preg_match('/^-?\d+/', $o->$textKey, $m) !== 1 || (int) $m[0] === $year) {
                continue;
            }
            $read = (int) $m[0];
            $lead = abs($read) === abs($year) ? 'BCE/CE sign mismatch: ' : '';
            $found[] = new RuleViolation("{$at}/{$textKey}", "{$lead}`{$textKey}` \"{$o->$textKey}\" reads as {$read}, but `{$yearKey}` is {$year}");
        }
    }
}
