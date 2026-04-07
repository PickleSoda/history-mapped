<?php

declare(strict_types=1);

namespace App\Models;

use App\Casts\GeoJson;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

#[Fillable([
    'entity_id',
    'entry_kind',
    'start_year',
    'end_year',
    'title',
    'description',
    'location_entity_id',
    'geom',
    'territory_geom',
    'source_table',
    'source_id',
    'relationship_type',
    'related_entity_id',
    'related_entity_name',
    'derived_at',
])]
class EntityTimelineEntry extends Model
{
    protected $table = 'entity_timeline_entries';

    protected $primaryKey = 'timeline_entry_id';

    public $incrementing = false;

    protected $keyType = 'string';

    protected function casts(): array
    {
        return [
            'geom' => GeoJson::class,
            'territory_geom' => GeoJson::class,
            'derived_at' => 'datetime',
        ];
    }

    // ── Relationships ─────────────────────────────────────────

    /** @return BelongsTo<Entity, $this> */
    public function entity(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'entity_id', 'entity_id');
    }

    /** @return BelongsTo<Entity, $this> */
    public function locationEntity(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'location_entity_id', 'entity_id');
    }

    /** @return BelongsTo<Entity, $this> */
    public function relatedEntity(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'related_entity_id', 'entity_id');
    }
}
