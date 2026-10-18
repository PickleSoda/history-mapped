<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Serializers;

use App\Models\EntityGeoRef;
use App\Support\ContentBundle\Profile;
use App\Support\ContentBundle\RecordType;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;

/**
 * Geo ref -> bundle line. The Public profile emits `source_meta` as null (the key set stays fixed).
 */
final class GeoRefSerializer implements RecordSerializer
{
    private const COLUMNS = [
        'geo_ref_id', 'entity_id', 'provider', 'external_type', 'external_id', 'match_role',
        'retrieval_method', 'temporal_start', 'temporal_end', 'temporal_start_year', 'temporal_end_year',
        'geometry_period_id', 'match_score', 'is_active', 'external_tags', 'source_meta',
    ];

    public function type(): RecordType
    {
        return RecordType::GeoRefs;
    }

    public function query(): Builder
    {
        return EntityGeoRef::query()->select((new EntityGeoRef)->qualifyColumns(self::COLUMNS));
    }

    public function serialize(Model $model, Profile $profile): array
    {
        assert($model instanceof EntityGeoRef);
        $r = fn (string $col) => Values::raw($model, $col);
        // PDO returns numeric(6,4) as a string; the bundle carries a JSON number.
        $score = $r('match_score');

        return [
            'id' => $r('geo_ref_id'),
            'entity_id' => $r('entity_id'),
            'provider' => $r('provider'),
            'external_type' => $r('external_type'),
            'external_id' => $r('external_id'),
            'match_role' => $r('match_role'),
            'retrieval_method' => $r('retrieval_method'),
            'temporal_start' => $r('temporal_start'),
            'temporal_end' => $r('temporal_end'),
            'temporal_start_year' => $r('temporal_start_year'),
            'temporal_end_year' => $r('temporal_end_year'),
            'geometry_period_id' => $r('geometry_period_id'),
            'match_score' => $score === null ? null : (float) $score,
            'is_active' => (bool) $r('is_active'),
            // The DB holds `[]` or `{}` for an empty external_tags; both are emitted as `{}`.
            'external_tags' => Values::jsonbObject($model, 'external_tags'),
            // Read even in Public so a dropped column still throws; only the value is withheld.
            'source_meta' => $this->sourceMeta($model, $profile),
        ];
    }

    private function sourceMeta(EntityGeoRef $ref, Profile $profile): mixed
    {
        $meta = Values::jsonbObject($ref, 'source_meta');

        return $profile === Profile::Public ? null : $meta;
    }
}
