<?php

declare(strict_types=1);

namespace App\Actions\GeometrySnapshot;

use App\Models\GeometrySnapshot;

/**
 * Delete a GeometrySnapshot.
 */
class DeleteSnapshotAction
{
    public function __invoke(GeometrySnapshot $snapshot): void
    {
        $snapshot->delete();
    }
}
