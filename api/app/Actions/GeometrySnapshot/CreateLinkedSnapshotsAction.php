<?php

declare(strict_types=1);

namespace App\Actions\GeometrySnapshot;

use App\Actions\Relationship\CreateAutoSnapshotAction;
use App\Models\EntityRelationship;
use App\Models\GeometrySnapshot;

/**
 * Compatibility wrapper around the relationship-level auto snapshot action.
 *
 * The implementation lives in the relationship action because it is triggered
 * during relationship creation, but this wrapper preserves the originally
 * planned GeometrySnapshot action naming.
 */
class CreateLinkedSnapshotsAction
{
    public function __construct(private readonly CreateAutoSnapshotAction $createAutoSnapshot) {}

    public function __invoke(EntityRelationship $relationship): ?GeometrySnapshot
    {
        return ($this->createAutoSnapshot)($relationship);
    }
}
