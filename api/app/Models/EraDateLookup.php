<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class EraDateLookup extends Model
{
    protected $table = 'ref_era_date_lookup';

    protected $primaryKey = 'lookup_id';

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
            'search_variants' => 'array',
        ];
    }

    // ── Relationships ────────────────────────────────────────

    /** @return BelongsTo<HistoricalPeriod, $this> */
    public function period(): BelongsTo
    {
        return $this->belongsTo(HistoricalPeriod::class, 'period_id', 'period_id');
    }
}
