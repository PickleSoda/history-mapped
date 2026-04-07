<?php

declare(strict_types=1);

namespace App\Actions\Relationship;

use App\DTOs\RelationshipData;
use App\Models\EntityRelationship;
use App\Models\GeometryPeriod;

/**
 * @deprecated Compatibility shim. Use CreateDerivedPresencePeriodAction directly.
 */
class CreateAutoSnapshotAction
{
    public function __construct(
        private readonly CreateDerivedPresencePeriodAction $createDerivedPresencePeriod,
    ) {}

    public function __invoke(EntityRelationship $relationship, RelationshipData $data, ?string $createdBy = null): ?GeometryPeriod
    {
        return ($this->createDerivedPresencePeriod)($relationship, $data, $createdBy);
    }
}
