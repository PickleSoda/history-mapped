<?php

declare(strict_types=1);

namespace App\Actions\GeometrySnapshot;

use App\Actions\EntityGeoRef\PruneOrphanSnapshotGeoRefAction;
use App\Models\GeometrySnapshot;
use Illuminate\Support\Facades\DB;

/**
 * Delete a GeometrySnapshot.
 */
class DeleteSnapshotAction
{
    public function __construct(
        private readonly PruneOrphanSnapshotGeoRefAction $pruneOrphanSnapshotGeoRef,
    ) {}

    public function __invoke(GeometrySnapshot $snapshot): void
    {
        DB::transaction(function () use ($snapshot): void {
            $geoRefId = $snapshot->geo_ref_id;
            $entityId = $snapshot->entity_id;

            $snapshot->delete();
            $this->pruneOrphanSnapshotGeoRef->__invoke($geoRefId, $entityId);
        });
    }
}
