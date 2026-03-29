<?php

declare(strict_types=1);

namespace App\Actions\GeometrySnapshot;

use App\DTOs\GeometrySnapshotData;
use App\Models\GeometrySnapshot;
use App\Support\Geometry\NormalizeGeoJsonForPostgis;
use Illuminate\Support\Facades\DB;

/**
 * Update an existing GeometrySnapshot.
 *
 * Uses a single UPDATE statement so that both geometry columns and scalar
 * columns are committed atomically — the gs_has_geometry CHECK constraint
 * is evaluated once per statement.
 */
class UpdateSnapshotAction
{
    public function __invoke(GeometrySnapshot $snapshot, GeometrySnapshotData $data): GeometrySnapshot
    {
        return DB::transaction(function () use ($snapshot, $data): GeometrySnapshot {
            $modelData = $data->toModelArray();
            $geojson = NormalizeGeoJsonForPostgis::normalize($data->geojson);
            $territoryGeojson = NormalizeGeoJsonForPostgis::normalize($data->territoryGeojson);
            unset($modelData['entity_id']); // entity_id is immutable after creation

            // Build SET clause items, collecting bindings in order
            $setClauses = [];
            $bindings = [];

            // Scalar fields from modelData
            $scalarMap = [
                'geo_ref_id' => 'geo_ref_id',
                'year_start' => 'year_start',
                'year_end' => 'year_end',
                'label' => 'label',
                'confidence' => 'confidence',
                'notes' => 'notes',
                'description' => 'description',
                'relationship_id' => 'relationship_id',
                'source_event_id' => 'source_event_id',
                'display_priority' => 'display_priority',
            ];

            foreach ($scalarMap as $modelKey => $column) {
                if (array_key_exists($modelKey, $modelData)) {
                    $setClauses[] = "{$column} = ?";
                    $bindings[] = $modelData[$modelKey];
                }
            }

            if (array_key_exists('source_citations', $modelData)) {
                $setClauses[] = 'source_citations = ?::jsonb';
                $bindings[] = json_encode($modelData['source_citations']);
            }

            // Geometry columns — only update if provided in the DTO
            if ($geojson !== null) {
                $setClauses[] = 'geom = ST_GeomFromGeoJSON(?)';
                $bindings[] = json_encode($geojson);
            }

            if ($territoryGeojson !== null) {
                $setClauses[] = 'territory_geom = ST_GeomFromGeoJSON(?)';
                $bindings[] = json_encode($territoryGeojson);
            }

            $setClauses[] = 'updated_at = ?';
            $bindings[] = now();

            // WHERE binding
            $bindings[] = $snapshot->snapshot_id;

            $sql = 'UPDATE geometry_snapshots SET ' . implode(', ', $setClauses) . ' WHERE snapshot_id = ?';

            DB::statement($sql, $bindings);

            return $snapshot->fresh();
        });
    }
}
