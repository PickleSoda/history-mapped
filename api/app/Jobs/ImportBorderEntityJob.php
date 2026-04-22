<?php

declare(strict_types=1);

namespace App\Jobs;

use App\Actions\Entity\CreateEntityAction;
use App\Actions\Entity\UpdateEntityAction;
use App\Actions\EntityGeoRef\CreateEntityGeoRefAction;
use App\Actions\EntityGeoRef\HydrateEntityGeometryFromGeoRefAction;
use App\DTOs\EntityData;
use App\Enums\GeoRefExternalType;
use App\Enums\GeoRefMatchRole;
use App\Enums\GeoRefProvider;
use App\Enums\GeoRefRetrievalMethod;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Models\GeometryPeriod;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Collection;

class ImportBorderEntityJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $tries = 3;

    public int $backoff = 10;

    /**
     * @param  array<string, mixed>  $record
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
            if (! isset($record['name'], $record['entity_type'], $record['entity_group'])) {
                Log::warning('[Borders] Skipped record missing required fields');

                return;
            }

            $geometryPeriods = is_array($record['_geometry_periods'] ?? null)
                ? $record['_geometry_periods']
                : [];
            $geometryPeriods = $this->filterValidGeometryPeriods($geometryPeriods);
            $geometryPeriods = $this->sortGeometryPeriods($geometryPeriods);

            $ohmRelationId = isset($record['_ohm_relation_id'])
                ? (string) $record['_ohm_relation_id']
                : null;

            $entityRecord = $record;
            unset($entityRecord['_geometry_periods'], $entityRecord['_ohm_relation_id']);
            $entityRecord['verification_status'] = 'ohm_draft';

            $entityData = EntityData::fromArray($entityRecord);

            $existingEntity = $this->findExistingEntity($record, $ohmRelationId);
            $entity = $existingEntity;
            if ($entity === null) {
                $entity = app(CreateEntityAction::class)->__invoke($entityData, "borders:{$this->batchId}");
                Log::info("[Borders] Imported: {$name} → {$entity->entity_id}");
            } elseif ($this->force) {
                $entity = app(UpdateEntityAction::class)->__invoke($entity, $entityData);
                Log::info("[Borders] Replaced: {$name} → {$entity->entity_id}");
            } else {
                Log::info("[Borders] Skipped duplicate: {$name}");
            }

            $persistedPeriods = $this->upsertGeometryPeriods($entity, $geometryPeriods, $this->batchId);

            $geoRef = null;
            if ($ohmRelationId !== null && $ohmRelationId !== '') {
                $geoRef = $this->firstOrCreateGeoRef($entity, $ohmRelationId, $geometryPeriods);
            }

            if ($geoRef !== null) {
                $this->attachGeometryPeriodGeoRefs($entity, $persistedPeriods);
            }

            if ($geoRef !== null) {
                $this->hydrateEntityGeometry($entity, $geoRef, $geometryPeriods);
            }
        } catch (\Throwable $e) {
            Log::error("[Borders] Failed to import {$name}: {$e->getMessage()}");

            throw $e;
        }
    }

    /**
     * @param  array<int, array<string, mixed>>  $geometryPeriods
     * @return array<int, array<string, mixed>>
     */
    private function sortGeometryPeriods(array $geometryPeriods): array
    {
        return Collection::make($geometryPeriods)
            ->sortBy([
                fn (array $period): int => isset($period['start_year']) ? (int) $period['start_year'] : PHP_INT_MAX,
                fn (array $period): int => isset($period['end_year']) ? (int) $period['end_year'] : PHP_INT_MAX,
                fn (array $period): string => isset($period['start_date']) ? (string) $period['start_date'] : '',
                fn (array $period): string => isset($period['end_date']) ? (string) $period['end_date'] : '',
            ])
            ->values()
            ->all();
    }

    /**
     * @param  array<int, array<string, mixed>>  $geometryPeriods
     * @return array<int, array<string, mixed>>
     */
    private function filterValidGeometryPeriods(array $geometryPeriods): array
    {
        return Collection::make($geometryPeriods)
            ->filter(function (array $period): bool {
                if (! isset($period['start_year'], $period['end_year'])) {
                    return true;
                }

                return (int) $period['start_year'] <= (int) $period['end_year'];
            })
            ->values()
            ->all();
    }

    /**
     * @param  array<string, mixed>  $record
     */
    private function findExistingEntity(array $record, ?string $ohmRelationId): ?Entity
    {
        $wikidataId = $record['wikidata_id'] ?? null;
        if (is_string($wikidataId) && $wikidataId !== '') {
            return Entity::query()->where('wikidata_id', $wikidataId)->first();
        }

        if ($ohmRelationId !== null && $ohmRelationId !== '') {
            $geoRef = EntityGeoRef::query()
                ->where('provider', GeoRefProvider::Ohm->value)
                ->where('external_type', GeoRefExternalType::Relation->value)
                ->where('external_id', $ohmRelationId)
                ->first();

            if ($geoRef !== null) {
                return Entity::query()->find($geoRef->entity_id);
            }
        }

        $name = $record['name'] ?? null;
        $type = $record['entity_type'] ?? null;

        if (is_string($name) && is_string($type) && $name !== '' && $type !== '') {
            return Entity::query()
                ->where('name', $name)
                ->where('entity_type', $type)
                ->first();
        }

        return null;
    }

    /**
     * @param  array<int, array<string, mixed>>  $geometryPeriods
     */
    private function firstOrCreateGeoRef(Entity $entity, string $ohmRelationId, array $geometryPeriods): EntityGeoRef
    {
        $existing = EntityGeoRef::query()
            ->where('entity_id', $entity->entity_id)
            ->where('provider', GeoRefProvider::Ohm->value)
            ->where('external_type', GeoRefExternalType::Relation->value)
            ->where('external_id', $ohmRelationId)
            ->whereNull('geometry_period_id')
            ->first();

        if ($existing !== null) {
            return $existing;
        }

        $first = $geometryPeriods[0] ?? [];
        $last = $geometryPeriods[count($geometryPeriods) - 1] ?? $first;

        return app(CreateEntityGeoRefAction::class)->__invoke($entity, [
            'provider' => GeoRefProvider::Ohm->value,
            'external_type' => GeoRefExternalType::Relation->value,
            'external_id' => $ohmRelationId,
            'match_role' => GeoRefMatchRole::Primary->value,
            'retrieval_method' => GeoRefRetrievalMethod::Overpass->value,
            'match_score' => 1.0,
            'is_active' => true,
            'temporal_start' => $first['start_date'] ?? null,
            'temporal_end' => $last['end_date'] ?? null,
            'temporal_start_year' => $first['start_year'] ?? null,
            'temporal_end_year' => $last['end_year'] ?? null,
            'external_tags' => [
                'admin_level' => '2',
                'import_batch' => $this->batchId,
            ],
            'source_meta' => [
                'source' => 'ohm_overpass',
            ],
        ]);
    }

    /**
     * @param  array<int, array{model: GeometryPeriod, source: array<string, mixed>}>  $persistedPeriods
     */
    private function attachGeometryPeriodGeoRefs(
        Entity $entity,
        array $persistedPeriods,
    ): void {
        foreach ($persistedPeriods as $entry) {
            $period = $entry['source'];
            $geometryPeriod = $entry['model'];
            $periodRelationId = isset($period['ohm_relation_id']) ? (string) $period['ohm_relation_id'] : null;

            if ($periodRelationId === null || $periodRelationId === '') {
                continue;
            }

            $existingPeriodRef = EntityGeoRef::query()
                ->where('entity_id', $entity->entity_id)
                ->where('provider', GeoRefProvider::Ohm->value)
                ->where('external_type', GeoRefExternalType::Relation->value)
                ->where('external_id', $periodRelationId)
                ->where('geometry_period_id', $geometryPeriod->geometry_period_id)
                ->first();

            if ($existingPeriodRef !== null) {
                continue;
            }

            app(CreateEntityGeoRefAction::class)->__invoke($entity, [
                'provider' => GeoRefProvider::Ohm->value,
                'external_type' => GeoRefExternalType::Relation->value,
                'external_id' => $periodRelationId,
                'geometry_period_id' => $geometryPeriod->geometry_period_id,
                'match_role' => GeoRefMatchRole::Candidate->value,
                'retrieval_method' => GeoRefRetrievalMethod::Overpass->value,
                'match_score' => 1.0,
                'is_active' => true,
                'temporal_start' => $period['start_date'] ?? null,
                'temporal_end' => $period['end_date'] ?? null,
                'temporal_start_year' => $period['start_year'] ?? null,
                'temporal_end_year' => $period['end_year'] ?? null,
                'external_tags' => is_array($period['external_tags'] ?? null)
                    ? $period['external_tags']
                    : ['admin_level' => '2'],
                'source_meta' => [
                    'source' => 'ohm_overpass',
                    'origin' => 'geometry_period',
                    'import_batch' => $this->batchId,
                ],
            ]);
        }
    }

    /**
     * @param  array<int, array<string, mixed>>  $geometryPeriods
     */
    private function hydrateEntityGeometry(Entity $entity, EntityGeoRef $geoRef, array $geometryPeriods): void
    {
        foreach ($geometryPeriods as $period) {
            $geojson = $period['geojson'] ?? null;
            if (is_array($geojson)) {
                app(HydrateEntityGeometryFromGeoRefAction::class)->__invoke($entity, $geoRef, $geojson, 'ohm_nominatim');

                return;
            }
        }
    }

    /**
     * @param  array<int, array<string, mixed>>  $periods
     */
    private function upsertGeometryPeriods(Entity $entity, array $periods, string $batchId): array
    {
        $persisted = [];

        foreach ($periods as $period) {
            $geojson = $period['geojson'] ?? null;
            if (! is_array($geojson)) {
                continue;
            }

            $startYear = isset($period['start_year']) ? (int) $period['start_year'] : null;
            $endYear = isset($period['end_year']) ? (int) $period['end_year'] : null;

            if ($startYear === null) {
                continue;
            }

            $description = $period['label'] ?? null;

            $existing = GeometryPeriod::query()
                ->where('entity_id', $entity->entity_id)
                ->where('start_year', $startYear)
                ->when($endYear !== null,
                    fn ($q) => $q->where('end_year', $endYear),
                    fn ($q) => $q->whereNull('end_year'),
                )
                ->where('provenance_mode', 'ohm_import')
                ->first();

            if ($existing !== null) {
                $persisted[] = [
                    'model' => $existing,
                    'source' => $period,
                ];

                continue;
            }

            $created = GeometryPeriod::query()->create([
                'entity_id' => $entity->entity_id,
                'period_type' => 'territory',
                'start_year' => $startYear,
                'end_year' => $endYear,
                'territory_geom' => $geojson,
                'description' => is_string($description) ? $description : null,
                'provenance_mode' => 'ohm_import',
                'confidence' => 'medium',
                'created_by' => "borders:{$batchId}",
            ]);

            $persisted[] = [
                'model' => $created,
                'source' => $period,
            ];
        }

        return $persisted;
    }
}
