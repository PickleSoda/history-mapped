<?php

declare(strict_types=1);

namespace App\Actions\EntityGeoRef;

use App\Enums\GeoRefMatchRole;
use App\Models\EntityGeoRef;
use App\Models\GeometrySnapshot;

class PruneOrphanSnapshotGeoRefAction
{
    public function __construct(
        private readonly DeleteEntityGeoRefAction $deleteEntityGeoRef,
    ) {}

    public function __invoke(?string $geoRefId, string $entityId): void
    {
        if ($geoRefId === null) {
            return;
        }

        $geoRef = EntityGeoRef::query()->find($geoRefId);

        if ($geoRef === null) {
            return;
        }

        $isReferencedBySnapshots = GeometrySnapshot::query()
            ->where('geo_ref_id', $geoRefId)
            ->exists();

        if ($isReferencedBySnapshots) {
            return;
        }

        $isPrimary = $geoRef->match_role === GeoRefMatchRole::Primary;
        $isEntityPrimary = $geoRef->entity()
            ->where('entities.entity_id', $entityId)
            ->where('entities.primary_geo_ref_id', $geoRefId)
            ->exists();

        if ($isPrimary || $isEntityPrimary) {
            return;
        }

        $this->deleteEntityGeoRef->__invoke($geoRef);
    }
}
