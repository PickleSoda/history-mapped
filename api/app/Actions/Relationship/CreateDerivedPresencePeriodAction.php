<?php

declare(strict_types=1);

namespace App\Actions\Relationship;

use App\DTOs\RelationshipData;
use App\Enums\RelationshipType;
use App\Models\Entity;
use App\Models\EntityRelationship;
use App\Models\GeometryPeriod;

class CreateDerivedPresencePeriodAction
{
    /** @var list<RelationshipType> */
    private const AUTO_PRESENCE_TYPES = [
        RelationshipType::FoughtAt,
        RelationshipType::SignedBy,
        RelationshipType::BornIn,
        RelationshipType::DiedIn,
        RelationshipType::ResidedIn,
    ];

    public function __invoke(EntityRelationship $relationship, RelationshipData $data, ?string $createdBy = null): ?GeometryPeriod
    {
        if (! in_array($data->relationshipType, self::AUTO_PRESENCE_TYPES, true)) {
            return null;
        }

        $sourceEntity = Entity::query()->withoutGlobalScopes()->find($relationship->source_entity_id);

        if ($sourceEntity === null || $sourceEntity->geom === null) {
            return null;
        }

        $startYear = $relationship->start_year;
        $endYear = $relationship->end_year ?? $startYear;

        if ($startYear === null || $endYear === null) {
            return null;
        }

        return GeometryPeriod::query()->create([
            'entity_id' => $relationship->source_entity_id,
            'period_type' => 'presence',
            'start_year' => $startYear,
            'end_year' => $endYear,
            'geom' => $sourceEntity->geom,
            'description' => $relationship->description,
            'provenance_mode' => 'derived',
            'relationship_id' => $relationship->relationship_id,
            'created_by' => $createdBy,
        ]);
    }
}
