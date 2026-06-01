<?php

declare(strict_types=1);

namespace App\Jobs;

use App\Actions\EntityGeoRef\ImportGeoResolutionAction;
use App\Actions\Entity\CreateEntityAction;
use App\Actions\Entity\UpdateEntityAction;
use App\DTOs\EntityData;
use App\Models\Entity;
use App\Models\EntityTemporalRange;
use App\Models\GeometryPeriod;
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
            unset($entityRecord['_relationship_hints'], $entityRecord['_geo_resolution']);

            if (isset($entityRecord['attributes']['_infobox'])) {
                unset($entityRecord['attributes']['_infobox']);
            }

            $entityRecord = $this->normalizePipelineRecord($entityRecord);

            // ── Ensure pipeline_draft status ────────────────────────────
            $entityRecord['verification_status'] = 'pipeline_draft';

            // ── Build EntityData DTO ────────────────────────────────────
            $entityData = EntityData::fromArray($entityRecord);

            // ── Create or overwrite ─────────────────────────────────────
            $existingEntity = $this->findExisting($record);

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
     * Find an existing entity by wikidata_id, or by exact name + type as fallback.
     */
    private function findExisting(array $record): ?Entity
    {
        $wikidataId = $record['wikidata_id'] ?? null;

        if ($wikidataId) {
            return Entity::query()->where('wikidata_id', $wikidataId)->first();
        }

        $name = $record['name'] ?? null;
        $type = $record['entity_type'] ?? null;

        if ($name && $type) {
            return Entity::query()
                ->where('name', $name)
                ->where('entity_type', $type)
                ->first();
        }

        return null;
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
