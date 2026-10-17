<?php

declare(strict_types=1);

namespace App\Models;

use App\Actions\Saved\ResolveSavedItemsAction;
use App\Enums\SaveableType;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;

/**
 * A user's star on an entity, chronicle or relationship. The target is a
 * (type, id) pair rather than an Eloquent morph so the stored type stays the
 * short API value; {@see ResolveSavedItemsAction} loads them.
 */
#[Fillable(['user_id', 'starrable_type', 'starrable_id'])]
class Star extends Model
{
    /** The target's summary card, filled for responses (not a column). */
    public ?array $resolvedItem = null;

    protected function casts(): array
    {
        return [
            'starrable_type' => SaveableType::class,
        ];
    }

    /** @return BelongsTo<User, $this> */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /** @return BelongsToMany<SavedFolder, $this> */
    public function folders(): BelongsToMany
    {
        return $this->belongsToMany(SavedFolder::class, 'saved_folder_star');
    }

    /** @param  Builder<Star>  $query */
    public function scopeForTarget(Builder $query, SaveableType $type, string $id): void
    {
        $query->where('starrable_type', $type->value)->where('starrable_id', $id);
    }
}
