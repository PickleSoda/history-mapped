<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class ReligiousTradition extends Model
{
    protected $table = 'ref_religious_traditions';

    protected $primaryKey = 'tradition_id';

    public $timestamps = false;

    protected $guarded = [];

    // ── Relationships ────────────────────────────────────────

    /** @return BelongsTo<ReligiousTradition, $this> */
    public function parent(): BelongsTo
    {
        return $this->belongsTo(ReligiousTradition::class, 'parent_tradition_id', 'tradition_id');
    }

    /** @return HasMany<ReligiousTradition, $this> */
    public function children(): HasMany
    {
        return $this->hasMany(ReligiousTradition::class, 'parent_tradition_id', 'tradition_id');
    }
}
