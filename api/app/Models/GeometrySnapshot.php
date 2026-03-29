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
use Illuminate\Database\Query\Builder;

#[Fillable([
    'snapshot_id',
    'entity_id',
    'geo_ref_id',
    'year_start',
    'year_end',
    'label',
    'confidence',
    'source_citations',
    'notes',
    'description',
    'relationship_id',
    'source_event_id',
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

    /** @return BelongsTo<EntityRelationship, $this> */
    public function relationship(): BelongsTo
    {
        return $this->belongsTo(EntityRelationship::class, 'relationship_id', 'relationship_id');
    }

    /** @return BelongsTo<EntityGeoRef, $this> */
    public function geoRef(): BelongsTo
    {
        return $this->belongsTo(EntityGeoRef::class, 'geo_ref_id', 'geo_ref_id');
    }

    // ── Custom Query Builder ─────────────────────────────────

    /**
     * Create a new Eloquent query builder for the model.
     *
     * @param  Builder  $query
     * @return GeometrySnapshotBuilder<static>
     */
    public function newEloquentBuilder($query): GeometrySnapshotBuilder
    {
        return new GeometrySnapshotBuilder($query);
    }
}
