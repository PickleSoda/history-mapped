<?php

declare(strict_types=1);

namespace App\Models;

use App\Support\MapStory\MapStoryFile;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

/**
 * A step-by-step map story — a battle, an epidemic, a trade network, a
 * chronicle's map layer — attached to an entity, a chronicle, or both (at
 * least one). `document` is the map-story document
 * (App\Support\MapStory\MapStoryDocument) with its references resolved to
 * ids; `period_*`, `bbox` and, for an `ambient` story, `ambient_steps` are
 * precomputed from it (MapStoryAmbient).
 *
 * The row is the live copy: `map-stories:sync` loads resources/map-stories/
 * files into it, the admin editor and the AI agent save it
 * (SaveMapStoryAction, which keeps `map_story_revisions`), and
 * `map-stories:export` writes it back to its file. `file_hash` is the hash of
 * the file content last synced or exported (`synced_at`); a row edited since
 * (`edited_at` later) holds edits the file lacks — see isEdited().
 */
#[Fillable([
    'entity_id', 'chronicle_id', 'slug', 'kind', 'title', 'year', 'period_start', 'period_end', 'ambient', 'step_count',
    'document', 'ambient_steps', 'bbox', 'source_path', 'file_hash', 'synced_at', 'edited_at', 'edited_by',
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
            'synced_at' => 'datetime',
            'edited_at' => 'datetime',
        ];
    }

    /** Microseconds, so `edited_at` and `synced_at` order within a second (timestamp(6) columns). */
    public function getDateFormat(): string
    {
        return 'Y-m-d H:i:s.u';
    }

    /** Story JSON keeps its floats (`12.0`), slashes and characters as written (MapStoryFile). */
    protected function asJson($value, $flags = 0)
    {
        return parent::asJson($value, $flags | MapStoryFile::JSON_FLAGS);
    }

    /** Edited (admin, AI or a restore) since its file was last synced or exported. */
    public function isEdited(): bool
    {
        return $this->edited_at !== null && ($this->synced_at === null || $this->edited_at->greaterThan($this->synced_at));
    }

    /**
     * Stories with edits their file lacks.
     *
     * @param  Builder<MapStory>  $query
     * @return Builder<MapStory>
     */
    public function scopeEdited(Builder $query): Builder
    {
        return $query->whereNotNull('edited_at')
            ->where(fn (Builder $q) => $q->whereNull('synced_at')->orWhereColumn('edited_at', '>', 'synced_at'));
    }

    /** @return HasMany<MapStoryRevision, $this> newest first */
    public function revisions(): HasMany
    {
        return $this->hasMany(MapStoryRevision::class, 'map_story_id', 'story_id')->orderByDesc('id');
    }

    /** @return BelongsTo<User, $this> */
    public function editor(): BelongsTo
    {
        return $this->belongsTo(User::class, 'edited_by');
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
