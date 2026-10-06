<?php

declare(strict_types=1);

namespace App\Jobs;

use App\Actions\Entity\CreateEntityAction;
use App\Actions\Entity\UpdateEntityAction;
use App\Actions\EntityGeoRef\ImportGeoResolutionAction;
use App\DTOs\EntityData;
use App\Enums\VerificationStatus;
use App\Models\Entity;
use App\Models\EntityTemporalRange;
use App\Models\GeometryPeriod;
use App\Services\EntityReferenceResolver;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use JsonException;

/**
 * Import a single entity from a pipeline JSONL record.
 *
 * Validates the record, converts it to EntityData, calls CreateEntityAction,
 * and stores _relationship_hints in a staging table for later resolution.
 */
class ImportEntityJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $tries = 3;

    public int $backoff = 10;

    /**
     * @param  array<string, mixed>  $record  — Decoded JSONL entity record.
     * @param  string  $batchId  — Pipeline batch identifier.
     * @param  bool  $force  — Overwrite existing entity if one is found.
     */
    public function __construct(
        public readonly array $record,
        public readonly string $batchId,
        public readonly bool $force = false,
    ) {}

    public function handle(): void
    {
        $record = $this->record;
        $name = $record['name'] ?? 'unknown';

        try {
            // ── Validate minimum required fields ────────────────────────
            if (! isset($record['name'], $record['entity_type'], $record['entity_group'])) {
                Log::warning('[Pipeline] Skipped record missing required fields: '.json_encode(array_keys($record)));

                return;
            }

            // ── Strip pipeline-only fields before creating EntityData ───
            $relationshipHints = $record['_relationship_hints'] ?? [];
            $geoResolution = $record['_geo_resolution'] ?? null;

            $entityRecord = $record;
            unset($entityRecord['_relationship_hints'], $entityRecord['_geo_resolution'], $entityRecord['_identity_span']);

            if (isset($entityRecord['attributes']['_infobox'])) {
                unset($entityRecord['attributes']['_infobox']);
            }

            $entityRecord = $this->normalizePipelineRecord($entityRecord);

            // ── Status: pipeline_draft, or needs_review when the pipeline ─
            // committed the record unverified (campaign approval gate). No other
            // value is honoured: an import must never self-promote a row.
            $entityRecord['verification_status'] = ($record['verification_status'] ?? null) === VerificationStatus::NeedsReview->value
                ? VerificationStatus::NeedsReview->value
                : VerificationStatus::PipelineDraft->value;

            // ── Find the row to merge into (identity-guarded) ───────────
            ['entity' => $existingEntity, 'rejected_qid' => $rejectedQid, 'namesake' => $namesake] = $this->findExisting($record);

            if ($existingEntity === null && $namesake !== null) {
                // Same-name / same-QID rows exist but none (or several) are of
                // this record's era: a new entity whose identity is in doubt.
                $entityRecord['verification_status'] = VerificationStatus::NeedsReview->value;
                $flags = is_array($entityRecord['validation_flags'] ?? null) ? $entityRecord['validation_flags'] : [];
                $entityRecord['validation_flags'] = array_values(array_unique([...$flags, $namesake]));
            }

            if ($rejectedQid !== null) {
                // The QID already belongs to a row with a different name: the
                // record's QID is wrong (or that row is) — never write it here,
                // keep it for review instead.
                $entityRecord['wikidata_id'] = null;
                $entityRecord['attributes'] = [
                    ...(is_array($entityRecord['attributes'] ?? null) ? $entityRecord['attributes'] : []),
                    '_rejected_wikidata_id' => $rejectedQid,
                ];
            }

            // ── Build EntityData DTO ────────────────────────────────────
            $entityData = EntityData::fromArray($entityRecord);

            // ── Create or overwrite ─────────────────────────────────────
            if ($existingEntity !== null) {
                if (! $this->force) {
                    $wikidataId = $record['wikidata_id'] ?? 'no QID';
                    Log::info("[Pipeline] Skipped duplicate: {$name} ({$wikidataId})");

                    return;
                }

                $action = app(UpdateEntityAction::class);
                $entity = $action($existingEntity, $entityData);

                Log::info("[Pipeline] Replaced: {$name} → {$entity->entity_id}");

                // Re-stage relationship hints, clearing stale ones first
                if (! empty($relationshipHints)) {
                    if ($this->hasStagingTable()) {
                        DB::table('pipeline_relationship_hints')
                            ->where('source_entity_id', $entity->entity_id)
                            ->delete();
                    }

                    $this->stageRelationshipHints($entity->entity_id, $relationshipHints);
                }

                $this->importGeoResolution($entity, $geoResolution);
                $this->syncTemporalRangeFromRecord($entity, $entityRecord);
                $this->ensureGeometryPeriodFromPrimaryLocation($entity, $entityRecord);
            } else {
                $action = app(CreateEntityAction::class);
                $entity = $action($entityData, "pipeline:{$this->batchId}");

                Log::info("[Pipeline] Imported: {$name} → {$entity->entity_id}");

                if (! empty($relationshipHints)) {
                    $this->stageRelationshipHints($entity->entity_id, $relationshipHints);
                }

                $this->importGeoResolution($entity, $geoResolution);
                $this->syncTemporalRangeFromRecord($entity, $entityRecord);
                $this->ensureGeometryPeriodFromPrimaryLocation($entity, $entityRecord);
            }

        } catch (\Throwable $e) {
            Log::error("[Pipeline] Failed to import {$name}: {$e->getMessage()}", [
                'record' => array_diff_key($record, array_flip(['_relationship_hints'])),
                'exception' => $e->getTraceAsString(),
            ]);

            throw $e;
        }
    }

    /**
     * Find an existing entity, layering three dedup keys so the same polity
     * imported from two transcripts collapses to one row:
     *   1. wikidata_id (exact)
     *   2. OHM external_id — authoritative for OHM-resolved polities; two rows
     *      pointing at the same OHM feature are the same entity even when their
     *      Wikidata QIDs differ (e.g. "Tawantinsuyu" Q28573 vs Q6609847).
     *   3. name + type with overlapping era — merges the same polity (German
     *      Empire 1871–1918 ×2) while keeping distinct-era namesakes apart
     *      (German Empire vs Nazi "Deutsches Reich" 1933–1945).
     *
     * Critically, a wikidata_id MISS no longer short-circuits to null — it falls
     * through to the OHM-id and name+era checks (the previous behaviour created
     * the cross-transcript duplicates).
     *
     * Identity guard: a row found by QID or OHM id is only merged into when its
     * name/aliases match the record (EntityReferenceResolver::recordMatchesRow)
     * — pipeline QIDs are sometimes wrong ("World War I" carried World War II's
     * QID, "Romagna" shared Romania's OHM feature) and a --force merge would
     * overwrite the other entity's name/summary. A rejected QID is reported back
     * so the caller drops it from the record (it belongs to the other row).
     *
     * Temporal namesake guard (EntityReferenceResolver::temporalFit, keep in
     * sync with pipeline db_lookup): a QID / OHM / name match whose dates are
     * clearly incompatible with the record's (its temporal_start/end, else the
     * pipeline's `_identity_span`) is refused — 'Philip II' of Spain never
     * merges into the Macedonian. For date-checked types (persons, dynasties,
     * events…) the name path picks the date-compatible row among namesakes
     * (pickNamesake: a slightly different date still matches), and none /
     * several dated namesakes yield `namesake` = 'namesake_ambiguous' so the
     * new row is created as needs_review. Public so the command's pre-import
     * dedup (ImportEntitiesCommand::isDuplicate) applies the very same rules.
     *
     * @return array{entity: Entity|null, rejected_qid: string|null, namesake: string|null}
     */
    public function findExisting(array $record): array
    {
        $name = is_string($record['name'] ?? null) ? $record['name'] : '';
        $altNames = $this->identityAltNames($record);
        $rejectedQid = null;
        $namesake = null;
        $span = $this->recordSpan($record);

        $wikidataId = $record['wikidata_id'] ?? null;
        if ($wikidataId) {
            $byWikidata = Entity::query()->where('wikidata_id', $wikidataId)->with('primaryTemporalRange')->orderBy('created_at')->get();
            $otherEra = null;
            foreach ($byWikidata as $candidate) {
                if (EntityReferenceResolver::recordMatchesRow($name, $altNames, EntityReferenceResolver::namesOfRow($candidate->entity_id))) {
                    if ($this->ofAnotherEra($candidate, $span)) {
                        $otherEra ??= $candidate;

                        continue;
                    }

                    return ['entity' => $candidate, 'rejected_qid' => null, 'namesake' => null];
                }
            }
            if ($byWikidata->isNotEmpty()) {
                $rejectedQid = (string) $wikidataId;
                if ($otherEra !== null) {
                    $namesake = EntityReferenceResolver::NAMESAKE_AMBIGUOUS;
                    Log::warning("[Pipeline] Namesake guard: {$wikidataId} is '{$otherEra->name}' of another era (".EntityReferenceResolver::describeSpan($this->entitySpan($otherEra)).' vs '.EntityReferenceResolver::describeSpan($span).") — not merging '{$name}'; importing without the QID");
                } else {
                    Log::warning("[Pipeline] Identity guard: {$wikidataId} is '{$byWikidata->first()->name}', not '{$name}' — not merging; importing without the QID");
                }
            }
        }

        $ohmExternalId = $this->ohmExternalId($record);
        if ($ohmExternalId !== null) {
            $byOhm = Entity::query()
                ->whereHas('geoRefs', function ($query) use ($ohmExternalId) {
                    $query->where('provider', 'ohm')->where('external_id', $ohmExternalId);
                })
                ->orderBy('created_at')
                ->get();
            foreach ($byOhm as $candidate) {
                if (EntityReferenceResolver::recordMatchesRow($name, $altNames, EntityReferenceResolver::namesOfRow($candidate->entity_id))
                    && ! $this->ofAnotherEra($candidate, $span)) {
                    return ['entity' => $candidate, 'rejected_qid' => $rejectedQid, 'namesake' => null];
                }
            }
            if ($byOhm->isNotEmpty()) {
                Log::warning("[Pipeline] Identity guard: OHM {$ohmExternalId} is '{$byOhm->first()->name}', not '{$name}' (or of another era) — not merging");
            }
        }

        $name = $record['name'] ?? null;
        $type = $record['entity_type'] ?? null;
        if ($name && $type) {
            $startYear = $this->parseYear($record['temporal_start'] ?? null);
            $endYear = $this->parseYear($record['temporal_end'] ?? null);

            $candidates = Entity::query()
                ->where('name', $name)
                ->where('entity_type', $type)
                ->with('primaryTemporalRange')
                ->orderBy('created_at')
                ->orderBy('entity_id')
                ->get();

            if (array_key_exists((string) $type, EntityReferenceResolver::NAMESAKE_TOLERANCE_YEARS)) {
                // Date-checked type: namesakes are told apart by date, with the
                // type's tolerance (the same person with slightly different
                // dates still merges).
                $rows = $candidates->map(fn (Entity $c): array => [
                    'entity_id' => $c->entity_id,
                    'entity_type' => $type,
                    'start_year' => $c->primaryTemporalRange?->start_year,
                    'end_year' => $c->primaryTemporalRange?->end_year,
                ])->all();
                [$row, $verdict] = EntityReferenceResolver::pickNamesake(array_values($rows), $span, (string) $type);
                if ($row !== null) {
                    return ['entity' => $candidates->firstWhere('entity_id', $row['entity_id']), 'rejected_qid' => $rejectedQid, 'namesake' => null];
                }
                if ($verdict === EntityReferenceResolver::NAMESAKE_AMBIGUOUS) {
                    $namesake = $verdict;
                    Log::warning("[Pipeline] Namesake guard: {$candidates->count()} '{$name}' {$type} row(s) of other eras / several eras (record ".EntityReferenceResolver::describeSpan($span).') — importing a new row for review');
                }
            } else {
                foreach ($candidates as $candidate) {
                    if ($this->erasOverlap($startYear, $endYear, $candidate)) {
                        return ['entity' => $candidate, 'rejected_qid' => $rejectedQid, 'namesake' => null];
                    }
                }
            }
        }

        return ['entity' => null, 'rejected_qid' => $rejectedQid, 'namesake' => $namesake];
    }

    /**
     * The record's year span: its temporal_start/end, else the `_identity_span`
     * the pipeline derived for an undated record (its relations' dates).
     *
     * @return array{0: int, 1: int}|null
     */
    private function recordSpan(array $record): ?array
    {
        $span = EntityReferenceResolver::yearSpan(
            $this->parseYear($record['temporal_start'] ?? null),
            $this->parseYear($record['temporal_end'] ?? null),
        );
        if ($span !== null) {
            return $span;
        }

        $derived = $record['_identity_span'] ?? null;
        if (! is_array($derived)) {
            return null;
        }
        $derived = array_values($derived);

        return EntityReferenceResolver::yearSpan(
            $this->parseYear($derived[0] ?? null),
            $this->parseYear($derived[1] ?? null),
        );
    }

    /**
     * @return array{0: int, 1: int}|null
     */
    private function entitySpan(Entity $entity): ?array
    {
        $range = $entity->primaryTemporalRange;

        return EntityReferenceResolver::yearSpan($range?->start_year, $range?->end_year);
    }

    /**
     * Whether a row found by QID / OHM id is clearly of another era than the
     * record (a namesake): never merged into.
     *
     * @param  array{0: int, 1: int}|null  $span
     */
    private function ofAnotherEra(Entity $candidate, ?array $span): bool
    {
        $type = $candidate->entity_type instanceof \BackedEnum ? $candidate->entity_type->value : (string) $candidate->entity_type;

        return EntityReferenceResolver::temporallyIncompatible($type, $span, $this->entitySpan($candidate));
    }

    /**
     * The record's alternative names usable as identity evidence: the OHM
     * canonical name recorded as an alias by the pipeline's OHM match is left
     * out — it derives from the very match being checked, so two entities that
     * share a (wrong) OHM feature would otherwise "match" through it.
     *
     * @return list<string>
     */
    private function identityAltNames(array $record): array
    {
        $alts = array_values(array_filter(
            is_array($record['alternative_names'] ?? null) ? $record['alternative_names'] : [],
            static fn (mixed $a): bool => is_string($a) && trim($a) !== '',
        ));

        $display = $record['_geo_resolution']['geo_ref']['source_meta']['display_name'] ?? null;
        if (! is_string($display) || trim($display) === '') {
            return $alts;
        }
        $ohmName = mb_strtolower(trim(explode(',', $display)[0]));

        return array_values(array_filter($alts, static fn (string $a): bool => mb_strtolower(trim($a)) !== $ohmName));
    }

    /**
     * Extract the OHM feature id from the record's geo-resolution manifest.
     */
    private function ohmExternalId(array $record): ?string
    {
        $geoRef = $record['_geo_resolution']['geo_ref'] ?? null;
        if (! is_array($geoRef) || ($geoRef['provider'] ?? null) !== 'ohm') {
            return null;
        }

        $externalId = $geoRef['external_id'] ?? null;

        return is_string($externalId) && $externalId !== '' ? $externalId : null;
    }

    /**
     * Whether an incoming [start, end] era overlaps a candidate's primary range.
     * Missing bounds on either side are treated as "same entity" (lenient) so we
     * don't proliferate dateless duplicates; two fully-dated, non-overlapping
     * spans are kept separate.
     */
    private function erasOverlap(?int $start, ?int $end, Entity $candidate): bool
    {
        $range = $candidate->primaryTemporalRange;
        $candidateStart = $range?->start_year;
        $candidateEnd = $range?->end_year;

        if (($start === null && $end === null) || ($candidateStart === null && $candidateEnd === null)) {
            return true;
        }

        $s = $start ?? $end;
        $e = $end ?? $start;
        $cs = $candidateStart ?? $candidateEnd;
        $ce = $candidateEnd ?? $candidateStart;

        return max($s, $cs) <= min($e, $ce);
    }

    /**
     * Store relationship hints for later batch resolution.
     *
     * Uses a lightweight staging table. If the table doesn't exist,
     * falls back to the entity's attributes JSONB.
     */
    private function stageRelationshipHints(string $entityId, array $hints): void
    {
        // Try staging table first
        try {
            foreach ($hints as $hint) {
                DB::table('pipeline_relationship_hints')->insert([
                    'source_entity_id' => $entityId,
                    'relationship_type' => $hint['relationship_type'],
                    'target_wikidata_id' => $hint['target_wikidata_id'],
                    'target_label' => $hint['target_label'] ?? null,
                    'temporal_start' => $hint['temporal_start'] ?? null,
                    'temporal_end' => $hint['temporal_end'] ?? null,
                    'confidence' => $hint['confidence'] ?? 'medium',
                    'wikidata_property' => $hint['source'] ?? null,
                    'batch_id' => $this->batchId,
                    'resolved' => false,
                    'created_at' => now(),
                ]);
            }
        } catch (\Throwable $e) {
            // Fallback: store hints in entity attributes
            Log::debug("[Pipeline] Staging table not available, storing hints in attributes: {$e->getMessage()}");

            try {
                $encodedHints = json_encode($hints, JSON_THROW_ON_ERROR);

                DB::update(
                    "update entities
                    set attributes = jsonb_set(
                        jsonb_set(COALESCE(attributes, '{}'::jsonb), '{_relationship_hints}', ?::jsonb),
                        '{_relationship_hints_batch}',
                        to_jsonb(?::text)
                    )
                    where entity_id = ?",
                    [$encodedHints, $this->batchId, $entityId],
                );
            } catch (JsonException $jsonException) {
                Log::warning('[Pipeline] Failed to JSON-encode relationship hints for attribute fallback: '.$jsonException->getMessage(), [
                    'entity_id' => $entityId,
                ]);
            }
        }
    }

    private function hasStagingTable(): bool
    {
        try {
            return DB::getSchemaBuilder()->hasTable('pipeline_relationship_hints');
        } catch (\Throwable) {
            return false;
        }
    }

    private function importGeoResolution(Entity $entity, ?array $manifest): void
    {
        if ($manifest === null) {
            return;
        }

        try {
            app(ImportGeoResolutionAction::class)->__invoke($entity, $manifest);
        } catch (\Throwable $e) {
            Log::warning('[Pipeline] Geo-resolution import failed: '.$e->getMessage(), [
                'entity_id' => $entity->entity_id,
                'name' => $entity->name,
            ]);
        }
    }

    /**
     * @param  array<string, mixed>  $record
     * @return array<string, mixed>
     */
    private function normalizePipelineRecord(array $record): array
    {
        if (($record['location_name'] ?? null) === null && is_string($record['name'] ?? null) && trim((string) $record['name']) !== '') {
            $record['location_name'] = trim((string) $record['name']);
        }

        if (($record['temporal_start'] ?? null) === null) {
            $record['temporal_start'] = $record['attributes']['start_date'] ?? null;
        }

        if (($record['temporal_end'] ?? null) === null) {
            $record['temporal_end'] = $record['attributes']['end_date'] ?? null;
        }

        if (($record['impact_score'] ?? null) === null) {
            $record['impact_score'] = $this->deriveImpactScore($record);
        }

        // Map ordering (entities_display_priority_idx, NULLS LAST) needs a value;
        // the pipeline never sets one, leaving every row NULL. Seed it from the
        // derived impact so the most significant entities surface first.
        if (($record['display_priority'] ?? null) === null) {
            $record['display_priority'] = (int) $record['impact_score'];
        }

        return $record;
    }

    /**
     * @param  array<string, mixed>  $record
     */
    private function deriveImpactScore(array $record): int
    {
        $baseByType = [
            'political_entity' => 80,
            'event_war' => 76,
            'event_battle' => 74,
            'dynasty' => 72,
            'city' => 64,
            'infrastructure_monument' => 58,
        ];

        $entityType = is_string($record['entity_type'] ?? null) ? $record['entity_type'] : '';
        $score = $baseByType[$entityType] ?? 52;

        if (is_string($record['wikidata_id'] ?? null) && $record['wikidata_id'] !== '') {
            $score += 8;
        }

        if (is_string($record['summary'] ?? null) && trim($record['summary']) !== '') {
            $score += 4;
        }

        if (($record['temporal_start'] ?? null) !== null) {
            $score += 4;
        }

        if (($record['temporal_end'] ?? null) !== null) {
            $score += 2;
        }

        if (is_array($record['geojson'] ?? null)) {
            $score += 4;
        }

        return max(1, min(100, $score));
    }

    /**
     * @param  array<string, mixed>  $record
     */
    private function syncTemporalRangeFromRecord(Entity $entity, array $record): void
    {
        $temporalStart = $record['temporal_start'] ?? null;
        $temporalEnd = $record['temporal_end'] ?? null;

        if ($temporalStart === null && $temporalEnd === null) {
            return;
        }

        $startYear = $this->parseYear($temporalStart);
        $endYear = $this->parseYear($temporalEnd);

        // Defensive: a BCE year the pipeline emitted unsigned (e.g. "4000-01-01"
        // meaning 4000 BCE) can leave start_year > end_year and trip the
        // etr_valid_year_range check constraint, failing the whole entity import.
        // Drop the inconsistent end rather than losing the record.
        if ($startYear !== null && $endYear !== null && $startYear > $endYear) {
            Log::warning("[Pipeline] Dropping inconsistent temporal_end for {$entity->name}: start_year {$startYear} > end_year {$endYear}");
            $endYear = null;
            $temporalEnd = null;
        }

        EntityTemporalRange::query()->updateOrCreate(
            [
                'entity_id' => $entity->entity_id,
                'is_primary' => true,
            ],
            [
                'range_type' => 'primary',
                'start_year' => $startYear,
                'end_year' => $endYear,
                'start_date' => $this->stringOrNull($temporalStart),
                'end_date' => $this->stringOrNull($temporalEnd),
            ],
        );
    }

    /**
     * @param  array<string, mixed>  $record
     */
    private function ensureGeometryPeriodFromPrimaryLocation(Entity $entity, array $record): void
    {
        $entity = Entity::query()->with(['primaryLocation', 'primaryTemporalRange'])->find($entity->entity_id) ?? $entity;

        $primaryLocation = $entity->primaryLocation;
        if ($primaryLocation === null) {
            return;
        }

        $geom = $primaryLocation->geom;
        $territoryGeom = $primaryLocation->territory_geom;
        if (! is_array($geom) && ! is_array($territoryGeom)) {
            return;
        }

        $primaryRange = $entity->primaryTemporalRange;
        $startYear = $primaryRange?->start_year ?? $this->parseYear($record['temporal_start'] ?? null);
        $endYear = $primaryRange?->end_year ?? $this->parseYear($record['temporal_end'] ?? null);

        if ($startYear === null) {
            return;
        }

        $alreadyExists = GeometryPeriod::query()
            ->where('entity_id', $entity->entity_id)
            ->where('start_year', $startYear)
            ->when(
                $endYear !== null,
                fn ($query) => $query->where('end_year', $endYear),
                fn ($query) => $query->whereNull('end_year'),
            )
            ->whereIn('provenance_mode', ['pipeline_import', 'ohm_import', 'manual'])
            ->exists();

        if ($alreadyExists) {
            return;
        }

        GeometryPeriod::query()->create([
            'entity_id' => $entity->entity_id,
            'period_type' => 'territory',
            'start_year' => $startYear,
            'end_year' => $endYear,
            'geom' => is_array($geom) ? $geom : null,
            'territory_geom' => is_array($territoryGeom) ? $territoryGeom : null,
            'description' => 'Auto-generated from imported primary location',
            'provenance_mode' => 'ohm_import',
            'confidence' => 'medium',
            'created_by' => "pipeline:{$this->batchId}",
        ]);
    }

    private function parseYear(mixed $value): ?int
    {
        if (is_int($value)) {
            return $value;
        }

        if (! is_string($value) || trim($value) === '') {
            return null;
        }

        if (preg_match('/^-?\d+/', trim($value), $matches) !== 1) {
            return null;
        }

        return (int) $matches[0];
    }

    private function stringOrNull(mixed $value): ?string
    {
        if (is_string($value)) {
            $trimmed = trim($value);

            return $trimmed === '' ? null : $trimmed;
        }

        if (is_int($value) || is_float($value)) {
            return (string) $value;
        }

        return null;
    }
}
