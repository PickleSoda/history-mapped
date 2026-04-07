<?php

declare(strict_types=1);

namespace App\Actions\EntityModelV2;

use App\Models\Entity;

class BackfillGeometryPeriodsAction
{
    /**
     * Snapshot table was hard-removed earlier in this migration.
     * Geometry period backfill from snapshots is intentionally a no-op.
     */
    public function __invoke(Entity $entity): int
    {
        unset($entity);

        return 0;
    }
}
