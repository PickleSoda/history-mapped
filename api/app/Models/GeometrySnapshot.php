<?php

declare(strict_types=1);

namespace App\Models;

use App\Builders\GeometrySnapshotBuilder;
use App\Casts\GeoJson;
use App\Enums\ConfidenceLevel;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

#[Fillable([
    'snapshot_id',
    'entity_id',
    'year_start',
    'year_end',
    'label',
    'confidence',
    'source_citations',
    'notes',
    'display_priority',
    'created_by',
])]
class GeometrySnapshot extends Model
{
    use HasFactory;

    protected $table = 'geometry_snapshots';

    protected $primaryKey = 'snapshot_id';

    public $incrementing = false;

    protected $keyType = 'string';

    /**
     * Get the attributes that should be cast.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'geom' => GeoJson::class,
            'territory_geom' => GeoJson::class,
            'confidence' => ConfidenceLevel::class,
            'source_citations' => 'json',
            'year_start' => 'integer',
            'year_end' => 'integer',
            'display_priority' => 'integer',
        ];
    }

    // ── Relationships ────────────────────────────────────────

    /** @return BelongsTo<Entity, $this> */
    public function entity(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'entity_id', 'entity_id');
    }

    // ── Custom Query Builder ─────────────────────────────────

    /**
     * Create a new Eloquent query builder for the model.
     *
     * @param  \Illuminate\Database\Query\Builder  $query
     * @return GeometrySnapshotBuilder<static>
     */
    public function newEloquentBuilder($query): GeometrySnapshotBuilder
    {
        return new GeometrySnapshotBuilder($query);
    }
}
