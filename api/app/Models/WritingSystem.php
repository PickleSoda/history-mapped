<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class WritingSystem extends Model
{
    protected $table = 'ref_writing_systems';

    protected $primaryKey = 'system_id';

    public $timestamps = false;

    protected $guarded = [];

    /**
     * Get the attributes that should be cast.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'languages_using' => 'array',
            'still_in_use' => 'boolean',
        ];
    }

    // ── Relationships ────────────────────────────────────────

    /** @return BelongsTo<WritingSystem, $this> */
    public function derivedFrom(): BelongsTo
    {
        return $this->belongsTo(WritingSystem::class, 'derived_from_id', 'system_id');
    }
}
