<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class HistoricalPeriod extends Model
{
    protected $table = 'ref_historical_periods';

    protected $primaryKey = 'period_id';

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
            'alternative_names' => 'array',
        ];
    }

    // ── Relationships ────────────────────────────────────────

    /** @return BelongsTo<HistoricalPeriod, $this> */
    public function parent(): BelongsTo
    {
        return $this->belongsTo(HistoricalPeriod::class, 'parent_period_id', 'period_id');
    }

    /** @return HasMany<HistoricalPeriod, $this> */
    public function children(): HasMany
    {
        return $this->hasMany(HistoricalPeriod::class, 'parent_period_id', 'period_id');
    }

    /** @return BelongsTo<GeographicRegion, $this> */
    public function region(): BelongsTo
    {
        return $this->belongsTo(GeographicRegion::class, 'region_id', 'region_id');
    }
}
