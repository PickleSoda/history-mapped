<?php

declare(strict_types=1);

namespace App\Actions\Relationship;

use App\DTOs\RelationshipData;
use App\Models\EntityRelationship;

/**
 * Create a new relationship between two entities.
 */
class CreateRelationshipAction
{
    public function __invoke(RelationshipData $data, ?string $createdBy = null): EntityRelationship
    {
        $modelData = $data->toModelArray();

        if ($createdBy !== null) {
            $modelData['created_by'] = $createdBy;
        }

        return EntityRelationship::create($modelData);
    }
}
