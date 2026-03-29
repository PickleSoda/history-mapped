<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\GeoRefExternalType;
use App\Enums\GeoRefMatchRole;
use App\Enums\GeoRefProvider;
use App\Enums\GeoRefRetrievalMethod;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

#[Fillable([
    'geo_ref_id',
    'entity_id',
    'provider',
    'external_type',
    'external_id',
    'match_role',
    'retrieval_method',
    'temporal_start',
    'temporal_end',
    'temporal_start_year',
    'temporal_end_year',
    'external_tags',
    'source_meta',
    'match_score',
    'is_active',
])]
class EntityGeoRef extends Model
{
    use HasFactory;

    protected $table = 'entity_geo_refs';

    protected $primaryKey = 'geo_ref_id';

    public $incrementing = false;

    protected $keyType = 'string';

    /**
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'provider' => GeoRefProvider::class,
            'external_type' => GeoRefExternalType::class,
            'match_role' => GeoRefMatchRole::class,
            'retrieval_method' => GeoRefRetrievalMethod::class,
            'external_tags' => 'json',
            'source_meta' => 'json',
            'temporal_start_year' => 'integer',
            'temporal_end_year' => 'integer',
            'match_score' => 'decimal:4',
            'is_active' => 'boolean',
        ];
    }

    /** @return BelongsTo<Entity, $this> */
    public function entity(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'entity_id', 'entity_id');
    }

    /** @return HasMany<GeometrySnapshot, $this> */
    public function geometrySnapshots(): HasMany
    {
        return $this->hasMany(GeometrySnapshot::class, 'geo_ref_id', 'geo_ref_id');
    }
}
