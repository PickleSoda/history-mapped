<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

use App\Support\ContentBundle\BundleReader;
use App\Support\ContentBundle\RecordType;

/**
 * The records layer: rules that look at one line (year order, text year against integer year, the CHECK
 * constraints the database enforces) or at duplicates across a file. Streams each file once and keeps only
 * first-seen line numbers keyed by compact hashes. It runs only when the structure layer found no errors, so
 * every line decodes to an object of the right shape.
 *
 * The CHECK rules are evaluated on new-record and `replace` lines with absent keys read as null. A `merge`
 * line is checked only when every key of the rule is present; a partial merge is checked against the merged
 * value by the import planner. Nested `locations` always replace the whole list, so they are always checked.
 */
final class RecordChecks implements ValidationLayer
{
    public function name(): string
    {
        return Issue::RECORDS;
    }

    public function run(BundleReader $bundle, IssueSink $sink, bool $againstSite): void
    {
        foreach (RecordType::cases() as $type) {
            if ($bundle->has($type->file())) {
                $this->file($bundle, $sink, $type);
            }
        }
    }

    private function file(BundleReader $bundle, IssueSink $sink, RecordType $type): void
    {
        $file = $type->file();
        /** @var array<string, int> $ids */
        $ids = [];
        /** @var array<string, int> $unique relationship keys, chronicle slugs or wikidata ids, by first line */
        $unique = [];

        foreach ($bundle->lines($file) as $n => $line) {
            $d = json_decode($line, false);
            if (! $d instanceof \stdClass) {
                continue;
            }
            $id = isset($d->id) && is_string($d->id) ? $d->id : null;
            $delete = ($d->_op ?? null) === 'delete';
            $problems = [];

            if ($id !== null) {
                $key = strtolower($id);
                if (isset($ids[$key])) {
                    $problems[] = [Issue::ERROR, "duplicate id {$id} (lines {$ids[$key]} and {$n})", '/id'];
                } else {
                    $ids[$key] = $n;
                }
            }

            if (! $delete) {
                $this->duplicates($type, $d, $n, $unique, $problems);
                $this->years($type, $d, $problems);
                $this->checks($type, $d, $id === null, $problems);
            }

            $hash = null;
            foreach ($problems as [$severity, $message, $field]) {
                $issue = $severity === Issue::ERROR
                    ? Issue::error(Issue::RECORDS, $message, $file, $n, $field, $id)
                    : Issue::warning(Issue::RECORDS, $message, $file, $n, $field, $id);
                $sink->add($issue, $hash ??= sha1($line, true));
            }
        }
    }

    /**
     * @param  array<string, int>  $unique
     * @param  list<array{string, string, string}>  $problems
     */
    private function duplicates(RecordType $type, \stdClass $d, int $n, array &$unique, array &$problems): void
    {
        if ($type === RecordType::Relationships) {
            $parts = [];
            foreach (['source_entity_id', 'target_entity_id', 'relationship_type'] as $k) {
                if (! isset($d->$k) || ! is_string($d->$k)) {
                    return;
                }
                $parts[] = strtolower($d->$k);
            }
            foreach (['start_year', 'end_year'] as $k) {
                $parts[] = isset($d->$k) ? (string) $d->$k : '';
            }
            $key = sha1(implode("\0", $parts), true);
            if (isset($unique[$key])) {
                $problems[] = [Issue::ERROR, "duplicate relationship: same source, target, type and years as line {$unique[$key]}", '/relationship_type'];
            } else {
                $unique[$key] = $n;
            }
        } elseif ($type === RecordType::Chronicles && isset($d->slug) && is_string($d->slug)) {
            if (isset($unique[$d->slug])) {
                $problems[] = [Issue::ERROR, "duplicate chronicle slug \"{$d->slug}\" (also on line {$unique[$d->slug]})", '/slug'];
            } else {
                $unique[$d->slug] = $n;
            }
        } elseif ($type === RecordType::Entities && isset($d->wikidata_id) && is_string($d->wikidata_id)) {
            $qid = strtoupper($d->wikidata_id);
            if (isset($unique[$qid])) {
                $problems[] = [Issue::WARNING, "wikidata_id {$d->wikidata_id} is also used on line {$unique[$qid]}", '/wikidata_id'];
            } else {
                $unique[$qid] = $n;
            }
        }
    }

    /** @param  list<array{string, string, string}>  $problems */
    private function years(RecordType $type, \stdClass $d, array &$problems): void
    {
        match ($type) {
            RecordType::Relationships => $this->yearPairs($d, '', 'start_year', 'end_year', 'temporal_start', 'temporal_end', $problems),
            RecordType::GeoRefs => $this->yearPairs($d, '', 'temporal_start_year', 'temporal_end_year', 'temporal_start', 'temporal_end', $problems),
            RecordType::GeometryPeriods, RecordType::Chronicles, RecordType::ChronicleEntries => $this->yearPairs($d, '', 'start_year', 'end_year', null, null, $problems),
            RecordType::Entities => null,
        };

        if ($type === RecordType::Entities && isset($d->temporal_ranges) && is_array($d->temporal_ranges)) {
            foreach ($d->temporal_ranges as $i => $range) {
                if ($range instanceof \stdClass) {
                    $this->yearPairs($range, "/temporal_ranges/{$i}", 'start_year', 'end_year', 'start_date', 'end_date', $problems);
                }
            }
        }
    }

    /** @param  list<array{string, string, string}>  $problems */
    private function yearPairs(\stdClass $o, string $at, string $startKey, string $endKey, ?string $startText, ?string $endText, array &$problems): void
    {
        $start = isset($o->$startKey) && is_int($o->$startKey) ? $o->$startKey : null;
        $end = isset($o->$endKey) && is_int($o->$endKey) ? $o->$endKey : null;
        if ($start !== null && $end !== null && $start > $end) {
            $problems[] = [Issue::ERROR, "{$startKey} {$start} is after {$endKey} {$end}", "{$at}/{$startKey}"];
        }

        foreach ([[$startText, $start, $startKey], [$endText, $end, $endKey]] as [$textKey, $year, $yearKey]) {
            if ($textKey === null || $year === null || ! isset($o->$textKey) || ! is_string($o->$textKey)) {
                continue;
            }
            if (preg_match('/^-?\d+/', $o->$textKey, $m) !== 1 || (int) $m[0] === $year) {
                continue;
            }
            $problems[] = [
                Issue::ERROR,
                abs((int) $m[0]) === abs($year)
                    ? "BCE/CE sign mismatch: text says {$m[0]}, year is {$year}"
                    : "year mismatch: text says {$m[0]}, year is {$year}",
                "{$at}/{$textKey}",
            ];
        }
    }

    /** @param  list<array{string, string, string}>  $problems */
    private function checks(RecordType $type, \stdClass $d, bool $isNew, array &$problems): void
    {
        if ($type === RecordType::GeometryPeriods) {
            $full = $isNew || ($d->_op ?? null) === 'replace';
            $has = fn (string ...$keys): bool => $full || count(array_filter($keys, fn ($k) => property_exists($d, $k))) === count($keys);

            if ($has('geom', 'territory_geom') && ($d->geom ?? null) === null && ($d->territory_geom ?? null) === null) {
                $problems[] = [Issue::ERROR, 'a geometry period needs `geom` or `territory_geom`', '/geom'];
            }
            if ($has('provenance_mode', 'relationship_id', 'source_event_id') && ($d->provenance_mode ?? null) === 'derived'
                && ($d->relationship_id ?? null) === null && ($d->source_event_id ?? null) === null) {
                $problems[] = [Issue::ERROR, 'a derived geometry period needs `relationship_id` or `source_event_id`', '/provenance_mode'];
            }
            if ($has('period_type', 'relationship_id') && ($d->period_type ?? null) === 'presence' && ($d->relationship_id ?? null) === null) {
                $problems[] = [Issue::ERROR, 'a presence geometry period needs `relationship_id`', '/relationship_id'];
            }
        }

        if ($type === RecordType::Entities && isset($d->locations) && is_array($d->locations)) {
            foreach ($d->locations as $i => $loc) {
                if ($loc instanceof \stdClass && ($loc->location_name ?? null) === null && ($loc->geom ?? null) === null && ($loc->territory_geom ?? null) === null) {
                    $problems[] = [Issue::ERROR, 'a location needs `location_name`, `geom` or `territory_geom`', "/locations/{$i}"];
                }
            }
        }
    }
}
