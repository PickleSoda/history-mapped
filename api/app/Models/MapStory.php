<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * A step-by-step battle (or siege, naval battle, campaign) map attached to an
 * entity. `document` is the schema-1 map-story document
 * (App\Support\MapStory\MapStoryDocument) with its Q-ids resolved to entity
 * ids; rows are written by `map-stories:sync` from resources/map-stories/.
 */
#[Fillable([
    'entity_id', 'slug', 'kind', 'title', 'year', 'step_count', 'document', 'source_path', 'content_hash',
])]
class MapStory extends Model
{
    use HasUuids;

    protected $table = 'map_stories';

    protected $primaryKey = 'story_id';

    /** Columns for list views (everything but the document). */
    public const SUMMARY_COLUMNS = ['story_id', 'entity_id', 'slug', 'kind', 'title', 'year', 'step_count'];

    protected function casts(): array
    {
        return [
            'year' => 'integer',
            'step_count' => 'integer',
            // An object, not an array: keeps empty JSON objects (`positions: {}`) as {}.
            'document' => 'object',
        ];
    }

    /** @return BelongsTo<Entity, $this> */
    public function entity(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'entity_id', 'entity_id');
    }
}
