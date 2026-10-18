<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Serializers;

use App\Models\EntityRelationship;
use App\Support\ContentBundle\Profile;
use App\Support\ContentBundle\RecordType;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;

/**
 * Relationship -> bundle line. No nested lists, so one query exports any number of rows.
 */
final class RelationshipSerializer implements RecordSerializer
{
    private const COLUMNS = [
        'relationship_id', 'source_entity_id', 'target_entity_id', 'relationship_type', 'temporal_start',
        'temporal_end', 'start_year', 'end_year', 'description', 'confidence', 'derive_geometry_period',
        'source_citations',
    ];

    public function type(): RecordType
    {
        return RecordType::Relationships;
    }

    public function query(): Builder
    {
        return EntityRelationship::query()->select(self::COLUMNS);
    }

    public function serialize(Model $model, Profile $profile): array
    {
        assert($model instanceof EntityRelationship);
        $r = fn (string $col) => Values::raw($model, $col);

        return [
            'id' => $r('relationship_id'),
            'source_entity_id' => $r('source_entity_id'),
            'target_entity_id' => $r('target_entity_id'),
            'relationship_type' => $r('relationship_type'),
            'temporal_start' => $r('temporal_start'),
            'temporal_end' => $r('temporal_end'),
            'start_year' => $r('start_year'),
            'end_year' => $r('end_year'),
            'description' => $r('description'),
            'confidence' => $r('confidence'),
            'derive_geometry_period' => (bool) $r('derive_geometry_period'),
            'source_citations' => Values::jsonbObject($model, 'source_citations'),
        ];
    }
}
