<?php

declare(strict_types=1);

namespace App\Actions\Relationship;

use App\DTOs\RelationshipData;
use App\Models\EntityRelationship;

/**
 * Create a new relationship between two entities.
 *
 * After creation, attempts to auto-generate a presence snapshot if the
 * relationship type is one of the 11 auto-snapshot types.
 */
class CreateRelationshipAction
{
    public function __construct(private readonly CreateAutoSnapshotAction $autoSnapshot) {}

    public function __invoke(RelationshipData $data, ?string $createdBy = null): EntityRelationship
    {
        $modelData = $data->toModelArray();

        if ($createdBy !== null) {
            $modelData['created_by'] = $createdBy;
        }

        $relationship = EntityRelationship::create($modelData);

        // Eager-load related entities for the auto-snapshot check
        $relationship->load(['sourceEntity', 'targetEntity']);

        ($this->autoSnapshot)($relationship);

        return $relationship;
    }
}
