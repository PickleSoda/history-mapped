<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * A step-by-step map story — a battle, an epidemic, a trade network, a
 * chronicle's map layer — attached to an entity, a chronicle, or both (at
 * least one). `document` is the map-story document
 * (App\Support\MapStory\MapStoryDocument) with its references resolved to
 * ids; `period_*`, `bbox` and, for an `ambient` story, `ambient_steps` are
 * precomputed from it (MapStoryAmbient). Rows are written by
 * `map-stories:sync` from resources/map-stories/.
 */
#[Fillable([
    'entity_id', 'chronicle_id', 'slug', 'kind', 'title', 'year', 'period_start', 'period_end', 'ambient', 'step_count',
    'document', 'ambient_steps', 'bbox', 'source_path', 'content_hash',
])]
class MapStory extends Model
{
    use HasUuids;

    protected $table = 'map_stories';

    protected $primaryKey = 'story_id';

    /** Columns for list views (everything but the document). */
    public const SUMMARY_COLUMNS = ['story_id', 'entity_id', 'chronicle_id', 'slug', 'kind', 'title', 'year', 'step_count'];

    /** Columns for the story page (no precomputed ambient layer or extent). */
    public const DETAIL_COLUMNS = [...self::SUMMARY_COLUMNS, 'period_start', 'period_end', 'ambient', 'document'];

    protected function casts(): array
    {
        return [
            'year' => 'integer',
            'period_start' => 'integer',
            'period_end' => 'integer',
            'ambient' => 'boolean',
            'step_count' => 'integer',
            // An object, not an array: keeps empty JSON objects (`positions: {}`) as {}.
            'document' => 'object',
            'ambient_steps' => 'array',
        ];
    }

    /** @return BelongsTo<Entity, $this> */
    public function entity(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'entity_id', 'entity_id');
    }

    /** @return BelongsTo<Chronicle, $this> */
    public function chronicle(): BelongsTo
    {
        return $this->belongsTo(Chronicle::class, 'chronicle_id', 'chronicle_id');
    }
}
