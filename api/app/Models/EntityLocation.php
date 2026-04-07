<?php

declare(strict_types=1);

namespace App\Models;

use App\Casts\GeoJson;
use App\Enums\ConfidenceLevel;
use App\Enums\LocationResolutionMethod;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

#[Fillable([
    'entity_id',
    'location_name',
    'location_method',
    'location_confidence',
    'is_primary',
    'notes',
])]
class EntityLocation extends Model
{
    protected $table = 'entity_locations';

    protected $primaryKey = 'location_id';

    public $incrementing = false;

    protected $keyType = 'string';

    protected function casts(): array
    {
        return [
            'location_method' => LocationResolutionMethod::class,
            'location_confidence' => ConfidenceLevel::class,
            'geom' => GeoJson::class,
            'territory_geom' => GeoJson::class,
            'is_primary' => 'boolean',
        ];
    }

    /** @return BelongsTo<Entity, $this> */
    public function entity(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'entity_id', 'entity_id');
    }
}
