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

    public function supportsRelationshipType(RelationshipType $relationshipType): bool
    {
        return in_array($relationshipType, self::AUTO_PRESENCE_TYPES, true);
    }

    public function __invoke(EntityRelationship $relationship, RelationshipData $data, ?string $createdBy = null): ?GeometryPeriod
    {
        if (! $data->deriveGeometryPeriod) {
            return null;
        }

        $sourceEntity = Entity::query()
            ->withoutGlobalScopes()
            ->with('primaryLocation')
            ->find($relationship->source_entity_id);

        $targetEntity = Entity::query()
            ->withoutGlobalScopes()
            ->with('primaryLocation')
            ->find($relationship->target_entity_id);

        $targetLocation = $targetEntity?->primaryLocation;
        $sourceLocation = $sourceEntity?->primaryLocation;

        $derivedGeom = $targetLocation?->geom ?? $sourceLocation?->geom;
        $derivedTerritoryGeom = $targetLocation?->territory_geom ?? $sourceLocation?->territory_geom;

        if (($derivedGeom === null && $derivedTerritoryGeom === null)) {
            return null;
        }

        $startYear = $relationship->start_year;
        $endYear = $relationship->end_year ?? $startYear;

        if ($startYear === null || $endYear === null) {
            return null;
        }

        $attributes = [
            'entity_id' => $relationship->source_entity_id,
            'period_type' => 'presence',
            'start_year' => $startYear,
            'end_year' => $endYear,
            'geom' => $derivedGeom,
            'territory_geom' => $derivedTerritoryGeom,
            'description' => $relationship->description,
            'provenance_mode' => 'derived',
            'created_by' => $createdBy,
        ];

        $existing = GeometryPeriod::query()
            ->where('relationship_id', $relationship->relationship_id)
            ->where('period_type', 'presence')
            ->where('provenance_mode', 'derived')
            ->first();

        if ($existing !== null) {
            $existing->update($attributes);

            return $existing->refresh();
        }

        return GeometryPeriod::query()->create([
            ...$attributes,
            'relationship_id' => $relationship->relationship_id,
        ]);
    }
}
