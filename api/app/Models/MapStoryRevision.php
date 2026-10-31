<?php

declare(strict_types=1);

namespace App\Models;

use App\Support\MapStory\MapStoryFile;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * One saved version of a map story's authored document (no resolved ids),
 * written by SaveMapStoryAction on every admin save, AI update, sync update
 * and restore. The newest MAX_PER_STORY are kept.
 */
#[Fillable(['map_story_id', 'document', 'source', 'user_id', 'note'])]
class MapStoryRevision extends Model
{
    public const UPDATED_AT = null;

    public const MAX_PER_STORY = 50;

    /** Where a version came from. */
    public const SOURCES = ['admin', 'ai', 'sync', 'import', 'restore'];

    protected $table = 'map_story_revisions';

    protected function casts(): array
    {
        return [
            // An object, not an array: keeps empty JSON objects as {} and the key order.
            'document' => 'object',
            'created_at' => 'datetime',
        ];
    }

    /** Story JSON keeps its floats (`12.0`), slashes and characters as written (MapStoryFile). */
    protected function asJson($value, $flags = 0)
    {
        return parent::asJson($value, $flags | MapStoryFile::JSON_FLAGS);
    }

    /** @return BelongsTo<MapStory, $this> */
    public function story(): BelongsTo
    {
        return $this->belongsTo(MapStory::class, 'map_story_id', 'story_id');
    }

    /** @return BelongsTo<User, $this> */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class, 'user_id');
    }
}
