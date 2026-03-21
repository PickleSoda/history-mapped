<?php

declare(strict_types=1);

namespace App\Actions\Relationship;

use App\Actions\GeometrySnapshot\CreateSnapshotAction;
use App\DTOs\GeometrySnapshotData;
use App\Enums\RelationshipType;
use App\Models\EntityRelationship;
use App\Models\GeometrySnapshot;

/**
 * Auto-generate a presence snapshot on the source entity when a relationship
 * of an auto-snapshot type is created.
 *
 * The 11 auto-snapshot types indicate that the source entity was physically
 * present at the target entity's location. A point snapshot is created on the
 * source entity using its own geom, scoped to the relationship's temporal range.
 */
class CreateAutoSnapshotAction
{
    /**
     * The relationship types that trigger an automatic presence snapshot.
     *
     * @var list<RelationshipType>
     */
    private const AUTO_SNAPSHOT_TYPES = [
        RelationshipType::SignedBy,
        RelationshipType::Commanded,
        RelationshipType::FoughtAt,
        RelationshipType::VictoriousAt,
        RelationshipType::DefeatedAt,
        RelationshipType::Founded,
        RelationshipType::BornIn,
        RelationshipType::DiedIn,
        RelationshipType::ResidedIn,
        RelationshipType::MediatedBy,
        RelationshipType::GuaranteedBy,
    ];

    public function __construct(private readonly CreateSnapshotAction $createSnapshot) {}

    /**
     * Attempt to create an auto-snapshot for the given relationship.
     *
     * Returns the created snapshot, or null if conditions are not met:
     *   - relationship type is not in the auto-snapshot list
     *   - source entity has no point geom
     *   - no temporal range on the relationship
     */
    public function __invoke(EntityRelationship $relationship): ?GeometrySnapshot
    {
        if (! $this->shouldAutoSnapshot($relationship)) {
            return null;
        }

        $sourceEntity = $relationship->sourceEntity;
        $targetEntity = $relationship->targetEntity;

        if ($sourceEntity === null || $targetEntity === null) {
            return null;
        }

        // Require a point geometry on the source entity
        $geom = $sourceEntity->geom;
        if ($geom === null) {
            return null;
        }

        // Require at least a start year
        $temporalStart = $relationship->temporal_start;
        if ($temporalStart === null) {
            return null;
        }

        $yearStart = (int) $temporalStart;
        $yearEnd = $relationship->temporal_end !== null
            ? (int) $relationship->temporal_end
            : $yearStart;

        $typeName = $relationship->relationship_type instanceof RelationshipType
            ? $relationship->relationship_type->value
            : (string) $relationship->relationship_type;

        $description = sprintf(
            'Present at %s (%s)',
            $targetEntity->name,
            str_replace('_', ' ', $typeName),
        );

        $data = new GeometrySnapshotData(
            entityId: $sourceEntity->entity_id,
            yearStart: $yearStart,
            yearEnd: $yearEnd,
            geojson: is_array($geom) ? $geom : null,
            description: $description,
            relationshipId: $relationship->relationship_id,
        );

        return ($this->createSnapshot)($data);
    }

    private function shouldAutoSnapshot(EntityRelationship $relationship): bool
    {
        $type = $relationship->relationship_type;

        foreach (self::AUTO_SNAPSHOT_TYPES as $autoType) {
            if ($type === $autoType) {
                return true;
            }
        }

        return false;
    }
}
