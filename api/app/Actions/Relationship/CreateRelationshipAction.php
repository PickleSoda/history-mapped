<?php

declare(strict_types=1);

namespace App\Actions\Relationship;

use App\DTOs\RelationshipData;
use App\Models\EntityRelationship;
use Illuminate\Support\Str;

/**
 * Create a new relationship between two entities.
 */
class CreateRelationshipAction
{
    public function __construct(
        private readonly CreateAutoSnapshotAction $createAutoSnapshot,
    ) {}

    public function __invoke(RelationshipData $data, ?string $createdBy = null): EntityRelationship
    {
        $modelData = $data->toModelArray();
        $modelData['relationship_id'] = $modelData['relationship_id'] ?? Str::uuid()->toString();

        if ($createdBy !== null) {
            $modelData['created_by'] = $createdBy;
        }

        $relationship = EntityRelationship::create($modelData);

        // Triggers populate start_year/end_year from temporal text; refresh to expose persisted values.
        $relationship->refresh();

        ($this->createAutoSnapshot)($relationship, $data, $createdBy);

        return $relationship;
    }
}
