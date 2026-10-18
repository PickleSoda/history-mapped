<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

use App\Support\ContentBundle\BundleReader;
use App\Support\ContentBundle\RecordType;
use Illuminate\Support\Facades\DB;
use stdClass;
use Throwable;

/**
 * The references layer: every id a line points at must resolve, deletes must not leave dangling site rows,
 * same-owner foreign keys must hold and, with `--against-site`, geometries must be valid PostGIS input.
 *
 * Two passes over the record files keep memory flat (about 100 bytes per bundle record):
 *  1. Per type, `live` and `deleted` map id => `pack('N', line) . sha1(line, true)`; geo refs and geometry
 *     periods append the `entity_id` they set, which the same-owner rules need. The line number and hash
 *     let a cross-file issue name and downgrade the other line involved (IssueSink::addAcross()).
 *  2. Each non-delete line's reference fields are resolved. A target in the bundle is fine, one the bundle
 *     deletes is an error, any other is "outside": without a site it is only counted (one summary warning
 *     per file and field, as partial bundles legitimately point outside), with a site it is queued and
 *     checked in batches of SITE_BATCH ids per query.
 *
 * With a site, the deleted ids are first looked up in the rows that reference them (batched). A referring
 * row is excused when the bundle deletes it or re-points the field, which pass 2 learns while it streams
 * the lines of exactly those rows, so no per-line reference values are kept. Geometries are validated in
 * batches of GEOM_BATCH, each query in a savepoint; a batch that throws is retried one by one to find the
 * unreadable GeoJSON.
 */
final class ReferenceChecks implements ValidationLayer
{
    public const SITE_BATCH = 1000;

    public const GEOM_BATCH = 500;

    private const SITE_CACHE_MAX = 50_000;

    /** @var array<string, list<array{string, RecordType}>> source type => [field, target type] */
    private const REFS = [
        'entities' => [['primary_geo_ref_id', RecordType::GeoRefs]],
        'relationships' => [['source_entity_id', RecordType::Entities], ['target_entity_id', RecordType::Entities]],
        'geometry_periods' => [['entity_id', RecordType::Entities], ['source_event_id', RecordType::Entities], ['relationship_id', RecordType::Relationships]],
        'geo_refs' => [['entity_id', RecordType::Entities], ['geometry_period_id', RecordType::GeometryPeriods]],
        'chronicle_entries' => [['chronicle_id', RecordType::Chronicles], ['primary_relationship_id', RecordType::Relationships]],
    ];

    /** @var array<string, list<array{RecordType, ?string, string, string}>> deleted type => [row type, table (null = model table), pk column, reference column] */
    private const REFERRERS = [
        'entities' => [
            [RecordType::Relationships, null, 'relationship_id', 'source_entity_id'],
            [RecordType::Relationships, null, 'relationship_id', 'target_entity_id'],
            [RecordType::GeometryPeriods, null, 'geometry_period_id', 'entity_id'],
            [RecordType::GeometryPeriods, null, 'geometry_period_id', 'source_event_id'],
            [RecordType::GeoRefs, null, 'geo_ref_id', 'entity_id'],
            [RecordType::ChronicleEntries, 'chronicle_entry_entities', 'entry_id', 'entity_id'],
        ],
        'relationships' => [
            [RecordType::GeometryPeriods, null, 'geometry_period_id', 'relationship_id'],
            [RecordType::ChronicleEntries, null, 'entry_id', 'primary_relationship_id'],
        ],
        'geometry_periods' => [[RecordType::GeoRefs, null, 'geo_ref_id', 'geometry_period_id']],
        'geo_refs' => [[RecordType::Entities, null, 'entity_id', 'primary_geo_ref_id']],
    ];

    private IssueSink $sink;

    private bool $againstSite;

    /** @var array<string, array<string, string>> */
    private array $live = [];

    /** @var array<string, array<string, string>> */
    private array $deleted = [];

    /** @var array<string, array<string, list<array{string, string, string, bool, string}>>> row type => row id => [field, deleted type, deleted id, excused, label] */
    private array $candidates = [];

    /** @var array<string, array<string, list<array{string, int, string, string, ?string, bool, ?string}>>> target type => id => queued [file, line, field, hash, expected owner, owner only, record id] */
    private array $pending = [];

    /** @var array<string, array<string, string|false>> target type => id => site owner ('' when the type has none), or false when absent */
    private array $siteCache = [];

    private int $siteCacheSize = 0;

    /** @var array<string, array{int, int}> field => [count, first line] for the current file */
    private array $outside = [];

    /** @var list<array{string, int, string, string, string, ?string}> queued geometries [file, line, field, hash, json, record id] */
    private array $geoms = [];

    public function name(): string
    {
        return Issue::REFERENCES;
    }

    public function run(BundleReader $bundle, IssueSink $sink, bool $againstSite): void
    {
        $this->sink = $sink;
        $this->againstSite = $againstSite;
        $this->live = $this->deleted = $this->candidates = $this->pending = $this->siteCache = $this->geoms = $this->outside = [];
        $this->siteCacheSize = 0;

        foreach (RecordType::cases() as $type) {
            if ($bundle->has($type->file())) {
                $this->collect($bundle, $type);
            }
        }
        if ($againstSite) {
            $this->findSiteReferrers();
        }
        foreach (RecordType::cases() as $type) {
            if ($bundle->has($type->file())) {
                $this->check($bundle, $type);
            }
        }
        foreach (array_keys($this->pending) as $tv) {
            $this->flushPending($tv);
        }
        $this->flushGeoms();
        if ($againstSite) {
            $this->reportStillReferenced();
        }
    }

    private function collect(BundleReader $bundle, RecordType $type): void
    {
        $tv = $type->value;
        $this->live[$tv] ??= [];
        $this->deleted[$tv] ??= [];
        $ownerBearing = $type === RecordType::GeoRefs || $type === RecordType::GeometryPeriods;
        foreach ($bundle->lines($type->file()) as $n => $line) {
            $d = json_decode($line, false);
            if (! $d instanceof stdClass || ! isset($d->id) || ! is_string($d->id)) {
                continue;
            }
            $packed = pack('N', $n).sha1($line, true);
            if (($d->_op ?? null) === 'delete') {
                $this->deleted[$tv][strtolower($d->id)] = $packed;
            } else {
                $owner = $ownerBearing && isset($d->entity_id) && is_string($d->entity_id) ? strtolower($d->entity_id) : '';
                $this->live[$tv][strtolower($d->id)] = $packed.$owner;
            }
        }
    }

    private function check(BundleReader $bundle, RecordType $type): void
    {
        $tv = $type->value;
        $file = $type->file();
        $this->outside = [];

        foreach ($bundle->lines($file) as $n => $line) {
            $d = json_decode($line, false);
            if (! $d instanceof stdClass) {
                continue;
            }
            $op = $d->_op ?? null;
            if ($op === 'delete') {
                continue;
            }
            $id = isset($d->id) && is_string($d->id) ? strtolower($d->id) : null;
            if ($id !== null && isset($this->candidates[$tv][$id])) {
                $this->excuse($tv, $id, $d, $op);
            }

            foreach (self::REFS[$tv] ?? [] as [$field, $target]) {
                if (isset($d->$field) && is_string($d->$field)) {
                    // Same-owner rules: primary_geo_ref_id must belong to this entity, geometry_period_id to this geo ref's entity.
                    $expected = match (true) {
                        $type === RecordType::Entities => $id,
                        $type === RecordType::GeoRefs && $field === 'geometry_period_id' => isset($d->entity_id) && is_string($d->entity_id) ? strtolower($d->entity_id) : null,
                        default => null,
                    };
                    $this->reference($type, $n, $line, "/{$field}", $target, $d->$field, $expected, $id);
                }
            }
            if ($type === RecordType::ChronicleEntries && isset($d->entities) && is_array($d->entities)) {
                foreach ($d->entities as $i => $item) {
                    if ($item instanceof stdClass && isset($item->entity_id) && is_string($item->entity_id)) {
                        $this->reference($type, $n, $line, "/entities/{$i}/entity_id", RecordType::Entities, $item->entity_id, null, $id);
                    }
                }
            }

            if ($this->againstSite) {
                $this->queueGeometries($type, $n, $line, $d, $id);
            }
        }

        foreach ($this->outside as $field => [$count, $first]) {
            $label = str_contains($field, '/entities/') ? '/entities/*/entity_id' : $field;
            $this->sink->add(Issue::warning(Issue::REFERENCES, "{$count} references in `".ltrim($label, '/')."` point outside the bundle (first on line {$first}); they must exist on the site at import (run with --against-site to check them)", $file, null, $label));
        }
        $this->outside = [];
    }

    /** @param  ?string  $expectedOwner the entity that must own the target (same-owner rules), when known */
    private function reference(RecordType $type, int $n, string $line, string $field, RecordType $target, string $value, ?string $expectedOwner, ?string $id): void
    {
        $file = $type->file();
        $tv = $target->value;
        $key = strtolower($value);

        if (isset($this->deleted[$tv][$key])) {
            $this->sink->addAcross(
                Issue::error(Issue::REFERENCES, "references {$tv} {$value}, which this bundle deletes", $file, $n, $field, $id),
                [[$file, sha1($line, true)], [$target->file(), substr($this->deleted[$tv][$key], 4)]],
            );

            return;
        }

        if (isset($this->live[$tv][$key])) {
            $targetOwner = substr($this->live[$tv][$key], 24);
            if ($expectedOwner !== null && $targetOwner !== '') {
                if ($targetOwner !== $expectedOwner) {
                    $this->sink->addAcross(
                        Issue::error(Issue::REFERENCES, "references {$tv} {$value}, which belongs to entity {$targetOwner}, not entity {$expectedOwner}", $file, $n, $field, $id),
                        [[$file, sha1($line, true)], [$target->file(), substr($this->live[$tv][$key], 4, 20)]],
                    );
                }
            } elseif ($expectedOwner !== null && $this->againstSite) {
                // The bundle line for the target does not say who owns it; the site row does.
                $this->queue($tv, $key, $file, $n, $field, $line, $expectedOwner, true, $id);
            }

            return;
        }

        if (! $this->againstSite) {
            $this->outside[$field] ??= [0, $n];
            $this->outside[$field][0]++;

            return;
        }

        $this->queue($tv, $key, $file, $n, $field, $line, $expectedOwner, false, $id);
    }

    private function queue(string $tv, string $key, string $file, int $n, string $field, string $line, ?string $expectedOwner, bool $ownerOnly, ?string $id): void
    {
        $occurrence = [$file, $n, $field, sha1($line, true), $expectedOwner, $ownerOnly, $id];
        if (isset($this->siteCache[$tv][$key])) {
            $this->evaluate($tv, $key, $this->siteCache[$tv][$key], $occurrence);

            return;
        }
        $this->pending[$tv][$key][] = $occurrence;
        if (count($this->pending[$tv]) >= self::SITE_BATCH) {
            $this->flushPending($tv);
        }
    }

    private function flushPending(string $tv): void
    {
        $ids = array_keys($this->pending[$tv] ?? []);
        if ($ids === []) {
            return;
        }
        $type = RecordType::from($tv);
        $hasOwner = $type === RecordType::GeoRefs || $type === RecordType::GeometryPeriods;
        $found = [];
        $rows = DB::table($this->table($type))
            ->whereRaw("{$type->primaryKey()} = any(?::uuid[])", [self::pgArray($ids)])
            ->get($hasOwner ? [$type->primaryKey(), 'entity_id'] : [$type->primaryKey()]);
        foreach ($rows as $row) {
            $found[strtolower((string) $row->{$type->primaryKey()})] = $hasOwner ? strtolower((string) $row->entity_id) : '';
        }

        if ($this->siteCacheSize + count($ids) > self::SITE_CACHE_MAX) {
            $this->siteCache = [];
            $this->siteCacheSize = 0;
        }
        foreach ($ids as $key) {
            $this->siteCache[$tv][$key] = $found[$key] ?? false;
            $this->siteCacheSize++;
            foreach ($this->pending[$tv][$key] as $occurrence) {
                $this->evaluate($tv, $key, $found[$key] ?? false, $occurrence);
            }
        }
        $this->pending[$tv] = [];
    }

    /** @param  array{string, int, string, string, ?string, bool, ?string}  $occurrence */
    private function evaluate(string $tv, string $key, string|false $siteOwner, array $occurrence): void
    {
        [$file, $n, $field, $hash, $expected, $ownerOnly, $id] = $occurrence;
        if ($siteOwner === false) {
            if (! $ownerOnly) {
                $this->sink->add(Issue::error(Issue::REFERENCES, "references {$tv} {$key}, which is neither in the bundle nor on the site", $file, $n, $field, $id), $hash);
            }

            return;
        }
        if ($expected !== null && $siteOwner !== '' && $siteOwner !== $expected) {
            $this->sink->add(Issue::error(Issue::REFERENCES, "references {$tv} {$key}, which belongs to entity {$siteOwner}, not entity {$expected}", $file, $n, $field, $id), $hash);
        }
    }

    /** Looks up, per deleted id, the site rows that reference it; rows the bundle deletes are excused at once. */
    private function findSiteReferrers(): void
    {
        foreach (self::REFERRERS as $deletedType => $specs) {
            $ids = array_keys($this->deleted[$deletedType] ?? []);
            if ($ids === []) {
                continue;
            }
            foreach ($specs as [$rowType, $table, $pk, $column]) {
                $table ??= $this->table($rowType);
                $rv = $rowType->value;
                foreach (array_chunk($ids, self::SITE_BATCH) as $chunk) {
                    $rows = DB::table($table)->whereRaw("{$column} = any(?::uuid[])", [self::pgArray($chunk)])->get([$pk, $column]);
                    foreach ($rows as $row) {
                        $rowId = strtolower((string) $row->$pk);
                        if (isset($this->deleted[$rv][$rowId])) {
                            continue;
                        }
                        $isEntryEntity = $table === 'chronicle_entry_entities';
                        $this->candidates[$rv][$rowId][] = [
                            $isEntryEntity ? 'entities' : $column,
                            $deletedType,
                            strtolower((string) $row->$column),
                            false,
                            $isEntryEntity ? "chronicle_entries {$rowId}" : "{$rv} {$rowId}",
                        ];
                    }
                }
            }
        }
    }

    /** Marks the candidate references of a bundle line that re-points them. */
    private function excuse(string $tv, string $id, stdClass $d, mixed $op): void
    {
        foreach ($this->candidates[$tv][$id] as $k => [$field, , $deletedId]) {
            if ($field === 'entities') {
                $excused = isset($d->entities) && is_array($d->entities) && ! in_array($deletedId, array_map(
                    fn ($item) => $item instanceof stdClass && is_string($item->entity_id ?? null) ? strtolower($item->entity_id) : '',
                    $d->entities,
                ), true);
            } elseif (property_exists($d, $field)) {
                $excused = ! is_string($d->$field) || strtolower($d->$field) !== $deletedId;
            } else {
                $excused = $op === 'replace';
            }
            $this->candidates[$tv][$id][$k][3] = $excused;
        }
    }

    private function reportStillReferenced(): void
    {
        /** @var array<string, array<string, array{int, string}>> $counts */
        $counts = [];
        foreach ($this->candidates as $rows) {
            foreach ($rows as $refs) {
                foreach ($refs as [, $deletedType, $deletedId, $excused, $label]) {
                    if (! $excused) {
                        $counts[$deletedType][$deletedId] ??= [0, $label];
                        $counts[$deletedType][$deletedId][0]++;
                    }
                }
            }
        }
        foreach ($counts as $deletedType => $byId) {
            $file = RecordType::from($deletedType)->file();
            foreach ($byId as $deletedId => [$count, $example]) {
                $packed = $this->deleted[$deletedType][$deletedId];
                $line = unpack('N', $packed)[1];
                $this->sink->add(
                    Issue::error(Issue::REFERENCES, "{$count} site records still reference it (e.g. {$example}); delete or re-point them in this bundle", $file, $line, '/id', $deletedId),
                    substr($packed, 4, 20),
                );
            }
        }
    }

    private function queueGeometries(RecordType $type, int $n, string $line, stdClass $d, ?string $id): void
    {
        $found = [];
        if ($type === RecordType::GeometryPeriods) {
            foreach (['geom', 'territory_geom'] as $f) {
                if (($d->$f ?? null) instanceof stdClass) {
                    $found["/{$f}"] = $d->$f;
                }
            }
        } elseif ($type === RecordType::Entities && isset($d->locations) && is_array($d->locations)) {
            foreach ($d->locations as $i => $loc) {
                foreach (['geom', 'territory_geom'] as $f) {
                    if ($loc instanceof stdClass && ($loc->$f ?? null) instanceof stdClass) {
                        $found["/locations/{$i}/{$f}"] = $loc->$f;
                    }
                }
            }
        }
        foreach ($found as $field => $geometry) {
            $this->geoms[] = [$type->file(), $n, $field, sha1($line, true), (string) json_encode($geometry), $id];
            if (count($this->geoms) >= self::GEOM_BATCH) {
                $this->flushGeoms();
            }
        }
    }

    private function flushGeoms(): void
    {
        $batch = $this->geoms;
        $this->geoms = [];
        if ($batch === []) {
            return;
        }
        try {
            $results = $this->validGeometries(array_column($batch, 4));
        } catch (Throwable) {
            $results = [];
            foreach ($batch as $i => $row) {
                try {
                    $results[$i] = $this->validGeometries([$row[4]])[0];
                } catch (Throwable $e) {
                    $results[$i] = 'unreadable GeoJSON: '.self::postgresMessage($e);
                }
            }
        }
        foreach ($batch as $i => [$file, $n, $field, $hash, , $id]) {
            $result = $results[$i];
            if ($result !== null) {
                $message = str_starts_with($result, 'unreadable GeoJSON') ? $result : "invalid geometry: {$result}";
                $this->sink->add(Issue::error(Issue::REFERENCES, $message, $file, $n, $field, $id), $hash);
            }
        }
    }

    /**
     * @param  list<string>  $geojson
     * @return array<int, ?string> input position => PostGIS's reason when invalid, null when valid
     */
    private function validGeometries(array $geojson): array
    {
        $rows = DB::transaction(fn () => DB::select(
            'SELECT s.i, ST_IsValid(s.g) AS v, ST_IsValidReason(s.g) AS r FROM (SELECT t.i, ST_GeomFromGeoJSON(t.x) AS g FROM unnest(?::text[]) WITH ORDINALITY AS t(x, i)) s',
            [self::pgArray($geojson)],
        ));
        $out = [];
        foreach ($rows as $row) {
            $out[(int) $row->i - 1] = $row->v === true || $row->v === 't' ? null : (string) $row->r;
        }

        return $out;
    }

    private static function postgresMessage(Throwable $e): string
    {
        $message = ($e->getPrevious() ?? $e)->getMessage();
        if (preg_match('/ERROR:\s+(.+?)(?:\R|\(Connection:|$)/s', $message, $m) === 1) {
            return trim($m[1]);
        }

        return trim(strtok($message, "\n") ?: $message);
    }

    private function table(RecordType $type): string
    {
        $class = $type->modelClass();

        return (new $class)->getTable();
    }

    /** @param  list<string>  $values */
    private static function pgArray(array $values): string
    {
        return '{'.implode(',', array_map(fn (string $v) => '"'.addcslashes($v, '"\\').'"', $values)).'}';
    }
}
