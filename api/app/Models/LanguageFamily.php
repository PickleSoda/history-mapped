<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class LanguageFamily extends Model
{
    protected $table = 'ref_language_families';

    protected $primaryKey = 'family_id';

    public $timestamps = false;

    protected $guarded = [];

    // ── Relationships ────────────────────────────────────────

    /** @return BelongsTo<LanguageFamily, $this> */
    public function parent(): BelongsTo
    {
        return $this->belongsTo(LanguageFamily::class, 'parent_family_id', 'family_id');
    }

    /** @return HasMany<LanguageFamily, $this> */
    public function children(): HasMany
    {
        return $this->hasMany(LanguageFamily::class, 'parent_family_id', 'family_id');
    }
}
