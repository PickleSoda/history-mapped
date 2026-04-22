<?php

declare(strict_types=1);

namespace App\Models;

use App\Casts\GeoJson;
use App\Enums\ConfidenceLevel;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Support\Str;

#[Fillable([
    'geometry_period_id',
    'entity_id',
    'period_type',
    'start_year',
    'end_year',
    'geom',
    'territory_geom',
    'description',
    'provenance_mode',
    'relationship_id',
    'source_event_id',
    'confidence',
    'created_by',
])]
class GeometryPeriod extends Model
{
    protected $table = 'geometry_periods';

    protected $primaryKey = 'geometry_period_id';

    public $incrementing = false;

    protected $keyType = 'string';

    protected static function booted(): void
    {
        static::creating(function (self $period): void {
            if (! is_string($period->geometry_period_id) || $period->geometry_period_id === '') {
                $period->geometry_period_id = Str::uuid()->toString();
            }
        });
    }

    protected function casts(): array
    {
        return [
            'confidence' => ConfidenceLevel::class,
            'geom' => GeoJson::class,
            'territory_geom' => GeoJson::class,
        ];
    }

    // ── Relationships ─────────────────────────────────────────

    /** @return BelongsTo<Entity, $this> */
    public function entity(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'entity_id', 'entity_id');
    }

    /** @return BelongsTo<EntityRelationship, $this> */
    public function relationship(): BelongsTo
    {
        return $this->belongsTo(EntityRelationship::class, 'relationship_id', 'relationship_id');
    }

    /** @return BelongsTo<Entity, $this> */
    public function sourceEvent(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'source_event_id', 'entity_id');
    }
}
