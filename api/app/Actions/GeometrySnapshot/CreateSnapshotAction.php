<?php

declare(strict_types=1);

namespace App\Actions\GeometrySnapshot;

use App\DTOs\GeometrySnapshotData;
use App\Models\GeometrySnapshot;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/**
 * Create a new GeometrySnapshot with optional PostGIS geometries.
 *
 * Uses a single INSERT statement so that the gs_has_geometry CHECK constraint
 * is satisfied immediately — INSERT-then-UPDATE would violate the constraint
 * because PostgreSQL CHECK constraints are not deferrable.
 */
class CreateSnapshotAction
{
    public function __invoke(GeometrySnapshotData $data, ?string $createdBy = null): GeometrySnapshot
    {
        return DB::transaction(function () use ($data, $createdBy): GeometrySnapshot {
            $snapshotId = Str::uuid()->toString();
            $now = now();

            // Build the geometry expressions for the INSERT
            $geomExpr = $data->geojson !== null
                ? 'ST_GeomFromGeoJSON(?)'
                : 'NULL';

            $territoryGeomExpr = $data->territoryGeojson !== null
                ? 'ST_GeomFromGeoJSON(?)'
                : 'NULL';

            $sql = <<<SQL
                INSERT INTO geometry_snapshots
                    (snapshot_id, entity_id, year_start, year_end,
                     geom, territory_geom,
                     label, confidence, source_citations, notes, description,
                     relationship_id, source_event_id,
                     display_priority, created_by, created_at, updated_at)
                VALUES
                    (?, ?, ?, ?,
                     {$geomExpr}, {$territoryGeomExpr},
                     ?, ?, ?::jsonb, ?, ?,
                     ?, ?,
                     ?, ?, ?, ?)
                SQL;

            $modelData = $data->toModelArray();

            $bindings = [$snapshotId, $modelData['entity_id'], $modelData['year_start'], $modelData['year_end']];

            if ($data->geojson !== null) {
                $bindings[] = json_encode($data->geojson);
            }

            if ($data->territoryGeojson !== null) {
                $bindings[] = json_encode($data->territoryGeojson);
            }

            $bindings = array_merge($bindings, [
                $modelData['label'] ?? null,
                $modelData['confidence'] ?? null,
                isset($modelData['source_citations']) ? json_encode($modelData['source_citations']) : null,
                $modelData['notes'] ?? null,
                $modelData['description'] ?? null,
                $modelData['relationship_id'] ?? null,
                $modelData['source_event_id'] ?? null,
                $modelData['display_priority'],
                $createdBy,
                $now,
                $now,
            ]);

            DB::statement($sql, $bindings);

            return GeometrySnapshot::findOrFail($snapshotId);
        });
    }
}
