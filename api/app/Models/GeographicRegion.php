<?php

declare(strict_types=1);

namespace App\Models;

use App\Casts\GeoJson;
use App\Casts\PgTextArray;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class GeographicRegion extends Model
{
    protected $table = 'ref_geographic_regions';

    protected $primaryKey = 'region_id';

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
            'alternative_names' => PgTextArray::class,
            'modern_countries' => PgTextArray::class,
            'historical_names' => PgTextArray::class,
            'typical_periods' => PgTextArray::class,
            'bounding_box' => GeoJson::class,
            'center_point' => GeoJson::class,
        ];
    }

    // ── Relationships ────────────────────────────────────────

    /** @return BelongsTo<GeographicRegion, $this> */
    public function parent(): BelongsTo
    {
        return $this->belongsTo(GeographicRegion::class, 'parent_region_id', 'region_id');
    }

    /** @return HasMany<GeographicRegion, $this> */
    public function children(): HasMany
    {
        return $this->hasMany(GeographicRegion::class, 'parent_region_id', 'region_id');
    }
}
