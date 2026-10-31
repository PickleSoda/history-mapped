<?php

declare(strict_types=1);

namespace App\Actions\EntityGeoRef;

use App\Enums\GeoRefMatchRole;
use App\Enums\GeoRefProvider;
use App\Enums\GeoRefRetrievalMethod;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Support\OhmDate;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use RuntimeException;
use Throwable;

/**
 * Backfill OHM links from the JSONL written by `python -m pipeline ohm-links fetch` (spec D6).
 *
 * Pass 1 streams the file (records keyed by `type/id`, first occurrence wins) and keeps in
 * memory only the records that can match: those whose `type/id` already has an OHM ref, or
 * whose Wikidata id some entity carries. The rest are counted `unmatched` and dropped, so a
 * 60k-record file stays far below the CLI memory limit. Keeping the matchable records lets
 * those sharing a Wikidata id be ranked together. Pass 2, in one transaction (rolled back on
 * a dry run), fills temporal ranges and tags on existing OHM refs, then creates refs on
 * entities whose `wikidata_id` matches a record exactly.
 *
 * @phpstan-type OhmLinkRecord array{
 *     key: string, type: string, id: string, qid: ?string,
 *     start_date: ?string, end_date: ?string, start_year: ?int, end_year: ?int,
 *     invalid_years: bool, tags: array<string, mixed>
 * }
 */
class ImportOhmLinksAction
{
    /** Preference order when several OHM features share one Wikidata id. */
    private const TYPE_RANK = ['relation' => 0, 'way' => 1, 'node' => 2];

    private const CHUNK = 1000;

    public function __construct(private readonly CreateEntityGeoRefAction $createGeoRef) {}

    /**
     * @return array{records: int, refs_updated: int, refs_created: int, skipped_existing: int,
     *     invalid_years: int, qid_duplicates: int, unmatched: int, malformed: int}
     */
    public function __invoke(string $path, string $batchId, bool $dryRun, bool $overwriteYears, ?string $runId = null): array
    {
        $counters = [
            'records' => 0,
            'refs_updated' => 0,
            'refs_created' => 0,
            'skipped_existing' => 0,
            'invalid_years' => 0,
            'qid_duplicates' => 0,
            'unmatched' => 0,
            'malformed' => 0,
        ];

        $records = $this->load($path, $counters);

        $sourceMeta = ['source' => 'ohm-links', 'batch_id' => $batchId, 'run_id' => $runId ?? basename(dirname($path))];
        /** @var array<string, true> $matched record keys that found an existing ref or an entity */
        $matched = [];

        DB::beginTransaction();
        try {
            $this->updateExistingRefs($records, $overwriteYears, $counters, $matched);
            $this->linkByWikidataId($records, $sourceMeta, $counters, $matched);
        } catch (Throwable $e) {
            DB::rollBack();

            throw $e;
        }
        $dryRun ? DB::rollBack() : DB::commit();

        $counters['unmatched'] += count(array_diff_key($records, $matched));

        return $counters;
    }

    /**
     * Stream the file; count every distinct record but keep only the matchable ones.
     *
     * @param  array<string, int>  $counters
     * @return array<string, OhmLinkRecord>
     */
    private function load(string $path, array &$counters): array
    {
        $handle = @fopen($path, 'r');
        if ($handle === false) {
            throw new RuntimeException("Cannot open file: {$path}");
        }

        $refKeys = $this->existingOhmRefKeys();
        $qids = $this->entityWikidataIds();

        /** @var array<string, true> $seen */
        $seen = [];
        $records = [];
        try {
            while (($line = fgets($handle)) !== false) {
                $line = trim($line);
                if ($line === '') {
                    continue;
                }

                $record = $this->normalize(json_decode($line, true));
                if ($record === null) {
                    $counters['malformed']++;

                    continue;
                }
                if (isset($seen[$record['key']])) {
                    continue;
                }
                $seen[$record['key']] = true;

                if ($record['invalid_years']) {
                    $counters['invalid_years']++;
                }

                if (isset($refKeys[$record['key']]) || ($record['qid'] !== null && isset($qids[$record['qid']]))) {
                    $records[$record['key']] = $record;
                } else {
                    $counters['unmatched']++;
                }
            }
        } finally {
            fclose($handle);
        }

        $counters['records'] = count($seen);
        Log::info('ohm-links: records loaded', ['records' => $counters['records'], 'kept' => count($records)]);

        return $records;
    }

    /** @return array<string, int> `type/id` of every OHM node/way/relation ref, active or not */
    private function existingOhmRefKeys(): array
    {
        return DB::table('entity_geo_refs')
            ->selectRaw("external_type::text || '/' || external_id AS ref_key")
            ->where('provider', GeoRefProvider::Ohm->value)
            ->whereIn('external_type', array_keys(self::TYPE_RANK))
            ->distinct()
            ->pluck('ref_key')
            ->flip()
            ->all();
    }

    /** @return array<string, int> distinct entities.wikidata_id */
    private function entityWikidataIds(): array
    {
        return DB::table('entities')
            ->whereNotNull('wikidata_id')
            ->distinct()
            ->pluck('wikidata_id')
            ->flip()
            ->all();
    }

    /**
     * Validate one decoded line against the record contract and apply rule 1 (years).
     *
     * @return OhmLinkRecord|null
     */
    private function normalize(mixed $raw): ?array
    {
        if (! is_array($raw) || ! is_string($raw['osm_type'] ?? null)) {
            return null;
        }

        $type = $raw['osm_type'];
        $id = is_int($raw['osm_id'] ?? null) || is_string($raw['osm_id'] ?? null) ? (string) $raw['osm_id'] : '';
        if (OhmDate::signedOsmId($type, $id) === null) {
            return null;
        }

        $qid = $raw['wikidata_id'] ?? null;
        $startDate = is_string($raw['start_date'] ?? null) ? $raw['start_date'] : null;
        $endDate = is_string($raw['end_date'] ?? null) ? $raw['end_date'] : null;

        [$startYear, $endYear] = OhmDate::yearsFrom($startDate, $endDate);
        $invalidYears = $startYear !== null && $endYear !== null && $startYear > $endYear;

        return [
            'key' => "{$type}/{$id}",
            'type' => $type,
            'id' => $id,
            'qid' => is_string($qid) && preg_match('/^Q\d+\z/', $qid) === 1 ? $qid : null,
            'start_date' => $startDate,
            'end_date' => $endDate,
            'start_year' => $invalidYears ? null : $startYear,
            'end_year' => $invalidYears ? null : $endYear,
            'invalid_years' => $invalidYears,
            'tags' => is_array($raw['tags'] ?? null) ? $raw['tags'] : [],
        ];
    }

    /**
     * Rule 2: fill empty temporal fields and tags on every OHM ref (any entity, active or not)
     * that points at a record's feature.
     *
     * @param  array<string, OhmLinkRecord>  $records
     * @param  array<string, int>  $counters
     * @param  array<string, true>  $matched
     */
    private function updateExistingRefs(array $records, bool $overwriteYears, array &$counters, array &$matched): void
    {
        $idsByType = [];
        foreach ($records as $record) {
            $idsByType[$record['type']][] = $record['id'];
        }

        foreach ($idsByType as $type => $ids) {
            foreach (array_chunk($ids, self::CHUNK) as $chunk) {
                $refs = EntityGeoRef::query()
                    ->where('provider', GeoRefProvider::Ohm->value)
                    ->where('external_type', $type)
                    ->whereIn('external_id', $chunk)
                    ->get();

                foreach ($refs as $ref) {
                    $record = $records["{$type}/{$ref->external_id}"];
                    $matched[$record['key']] = true;

                    $this->fillEmptyFields($ref, $record, $overwriteYears);
                    if ($ref->isDirty()) {
                        $ref->save();
                        $counters['refs_updated']++;
                    }
                }
            }
        }
    }

    /**
     * @param  OhmLinkRecord  $record
     */
    private function fillEmptyFields(EntityGeoRef $ref, array $record, bool $overwriteYears): void
    {
        $recordHasYears = $record['start_year'] !== null || $record['end_year'] !== null;
        $refHasNoYears = $ref->temporal_start_year === null && $ref->temporal_end_year === null;
        if ($recordHasYears && ($refHasNoYears || $overwriteYears)) {
            $ref->temporal_start_year = $record['start_year'];
            $ref->temporal_end_year = $record['end_year'];
            if ($overwriteYears) {
                // Keep the raw strings in step with the replaced years.
                $ref->temporal_start = $record['start_date'];
                $ref->temporal_end = $record['end_date'];
            }
        }

        if ($ref->temporal_start === null && $record['start_date'] !== null) {
            $ref->temporal_start = $record['start_date'];
        }
        if ($ref->temporal_end === null && $record['end_date'] !== null) {
            $ref->temporal_end = $record['end_date'];
        }

        if (empty($ref->external_tags) && $record['tags'] !== []) {
            $ref->external_tags = $record['tags'];
        }
    }

    /**
     * Rule 3: create refs on entities whose wikidata_id equals a record's Wikidata id.
     *
     * @param  array<string, OhmLinkRecord>  $records
     * @param  array<string, string>  $sourceMeta
     * @param  array<string, int>  $counters
     * @param  array<string, true>  $matched
     */
    private function linkByWikidataId(array $records, array $sourceMeta, array &$counters, array &$matched): void
    {
        $recordsByQid = [];
        foreach ($records as $record) {
            if ($record['qid'] !== null) {
                $recordsByQid[$record['qid']][] = $record;
            }
        }

        foreach (array_chunk(array_keys($recordsByQid), self::CHUNK) as $qids) {
            $entities = Entity::query()
                ->select(['entity_id', 'wikidata_id', 'primary_geo_ref_id'])
                ->with('primaryTemporalRange')
                ->whereIn('wikidata_id', $qids)
                ->orderBy('entity_id')
                ->get();
            if ($entities->isEmpty()) {
                continue;
            }

            $entityIds = $entities->pluck('entity_id')->all();
            $existingKeys = EntityGeoRef::query()
                ->whereIn('entity_id', $entityIds)
                ->where('provider', GeoRefProvider::Ohm->value)
                ->get(['entity_id', 'external_type', 'external_id'])
                ->groupBy('entity_id')
                ->map(fn ($refs) => $refs->mapWithKeys(fn (EntityGeoRef $r): array => ["{$r->external_type->value}/{$r->external_id}" => true])->all());
            $withActivePrimary = EntityGeoRef::query()
                ->whereIn('entity_id', $entityIds)
                ->where('match_role', GeoRefMatchRole::Primary->value)
                ->where('is_active', true)
                ->pluck('entity_id')
                ->flip();

            foreach ($entities->groupBy('wikidata_id') as $qid => $group) {
                if ($group->count() > 1) {
                    $counters['qid_duplicates']++;
                    Log::warning('ohm-links: Wikidata id matches several entities', [
                        'wikidata_id' => $qid,
                        'entity_ids' => $group->pluck('entity_id')->all(),
                    ]);
                }

                foreach ($recordsByQid[$qid] as $record) {
                    $matched[$record['key']] = true;
                }

                foreach ($group as $entity) {
                    $existing = $existingKeys->get($entity->entity_id, []);
                    $hasActivePrimary = $entity->primary_geo_ref_id !== null || $withActivePrimary->has($entity->entity_id);
                    $this->linkEntity($entity, $recordsByQid[$qid], $existing, $hasActivePrimary, $sourceMeta, $counters);
                }
            }
        }
    }

    /**
     * @param  list<OhmLinkRecord>  $records
     * @param  array<string, true>  $existing  `type/id` keys of the entity's OHM refs, active or not
     * @param  array<string, string>  $sourceMeta
     * @param  array<string, int>  $counters
     */
    private function linkEntity(
        Entity $entity,
        array $records,
        array $existing,
        bool $hasActivePrimary,
        array $sourceMeta,
        array &$counters,
    ): void {
        $toCreate = [];
        foreach ($records as $record) {
            // Never re-create (or re-activate) a ref an editor already has, even an inactive one.
            if (isset($existing[$record['key']])) {
                $counters['skipped_existing']++;
            } else {
                $toCreate[] = $record;
            }
        }

        $range = $entity->primaryTemporalRange;
        $entityStart = $range?->start_year !== null ? (int) $range->start_year : null;
        $entityEnd = $range?->end_year !== null ? (int) $range->end_year : null;
        usort($toCreate, fn (array $a, array $b): int => $this->compareForPrimary($a, $b, $entityStart, $entityEnd));

        foreach ($toCreate as $index => $record) {
            $role = $index === 0 && ! $hasActivePrimary ? GeoRefMatchRole::Primary : GeoRefMatchRole::Candidate;

            ($this->createGeoRef)($entity, [
                'provider' => GeoRefProvider::Ohm->value,
                'external_type' => $record['type'],
                'external_id' => $record['id'],
                'match_role' => $role->value,
                'retrieval_method' => GeoRefRetrievalMethod::Overpass->value,
                'match_score' => 0.9,
                'is_active' => true,
                'temporal_start' => $record['start_date'],
                'temporal_end' => $record['end_date'],
                'temporal_start_year' => $record['start_year'],
                'temporal_end_year' => $record['end_year'],
                'external_tags' => $record['tags'],
                'source_meta' => $sourceMeta,
            ]);
            $counters['refs_created']++;
        }
    }

    /**
     * Order for picking the primary (first wins): relation before way before node; then a
     * record with at least one usable year before an undated one (no year, or both rejected
     * by rule 1); then the largest overlap with the entity's primary temporal range; then
     * the latest end; then the lowest OSM id.
     *
     * @param  OhmLinkRecord  $a
     * @param  OhmLinkRecord  $b
     */
    private function compareForPrimary(array $a, array $b, ?int $entityStart, ?int $entityEnd): int
    {
        $undated = fn (array $r): bool => $r['start_year'] === null && $r['end_year'] === null;

        return [self::TYPE_RANK[$a['type']], $undated($a), -$this->overlap($a, $entityStart, $entityEnd)]
                <=> [self::TYPE_RANK[$b['type']], $undated($b), -$this->overlap($b, $entityStart, $entityEnd)]
            ?: $this->compareEnds($b, $a)
            ?: (int) $a['id'] <=> (int) $b['id'];
    }

    /**
     * Earlier end first: by end year, then by the raw end date (so month and day decide
     * when the years tie). A missing end year counts as open, and a missing end date as
     * ongoing, later than any other end.
     *
     * @param  OhmLinkRecord  $a
     * @param  OhmLinkRecord  $b
     */
    private function compareEnds(array $a, array $b): int
    {
        return [$a['end_year'] ?? INF, $a['end_date'] === null] <=> [$b['end_year'] ?? INF, $b['end_date'] === null]
            ?: strcmp($a['end_date'] ?? '', $b['end_date'] ?? '');
    }

    /**
     * Overlap in years between the record's and the entity's ranges, null bounds open.
     * Negative for disjoint ranges (minus the gap), so a nearer feature still ranks higher.
     *
     * @param  OhmLinkRecord  $record
     */
    private function overlap(array $record, ?int $entityStart, ?int $entityEnd): float|int
    {
        $start = max($record['start_year'] ?? -INF, $entityStart ?? -INF);
        $end = min($record['end_year'] ?? INF, $entityEnd ?? INF);

        return $end - $start;
    }
}
