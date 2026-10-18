<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Serializers;

use App\Enums\TagSource;
use App\Models\Chronicle;
use App\Support\ContentBundle\Profile;
use App\Support\ContentBundle\RecordType;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\Relation;

/**
 * Chronicle -> bundle line. Tags are read from `chronicle_tags` rows (manual/curated only) with one
 * eager-load query.
 */
final class ChronicleSerializer implements RecordSerializer
{
    private const COLUMNS = [
        'chronicle_id', 'slug', 'title', 'source_type', 'source_reference', 'status', 'start_year',
        'end_year', 'impact_score', 'approximate_location', 'metadata',
    ];

    public function type(): RecordType
    {
        return RecordType::Chronicles;
    }

    public function query(): Builder
    {
        return Chronicle::query()
            ->select(self::COLUMNS)
            ->with(['tagRows' => fn (Relation $q) => $q
                ->select(['chronicle_id', 'tag', 'source'])
                ->whereIn('source', TagSource::exported())]);
    }

    public function serialize(Model $model, Profile $profile): array
    {
        assert($model instanceof Chronicle);
        $r = fn (string $col) => Values::raw($model, $col);

        return [
            'id' => $r('chronicle_id'),
            'slug' => $r('slug'),
            'title' => $r('title'),
            'source_type' => $r('source_type'),
            'source_reference' => $r('source_reference'),
            'status' => $r('status'),
            'start_year' => $r('start_year'),
            'end_year' => $r('end_year'),
            'impact_score' => $r('impact_score'),
            'approximate_location' => Values::jsonbObject($model, 'approximate_location'),
            'metadata' => Values::jsonbObject($model, 'metadata') ?? (object) [],
            'tags' => TagList::build($model->tagRows),
        ];
    }
}
