<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;

/** A user's named collection of starred items. */
#[Fillable(['user_id', 'name', 'description', 'color'])]
class SavedFolder extends Model
{
    /** Folders one account may create. */
    public const MAX_PER_USER = 100;

    /** @return BelongsTo<User, $this> */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /** @return BelongsToMany<Star, $this> */
    public function stars(): BelongsToMany
    {
        return $this->belongsToMany(Star::class, 'saved_folder_star');
    }
}
