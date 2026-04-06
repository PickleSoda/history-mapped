<?php

declare(strict_types=1);

namespace App\Models;

use App\Builders\EntityBuilder;
use App\Casts\GeoJson;
use App\Casts\PgTextArray;
use App\Enums\ConfidenceLevel;
use App\Enums\DateResolutionMethod;
use App\Enums\DurationType;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Enums\IconClass;
use App\Enums\LocationResolutionMethod;
use App\Enums\VerificationStatus;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;
use Illuminate\Database\Query\Builder;
use Pgvector\Laravel\HasNeighbors;
use Pgvector\Laravel\Vector;

#[Fillable([
    'entity_id',
    'name',
    'entity_type',
    'entity_group',
    'summary',
    'significance',
    'attributes',
    'tags',
    'impact_score',
    'wikidata_id',
    'temporal_start',
    'temporal_end',
    'temporal_start_year',
    'temporal_end_year',
    'location_name',
    'parent_entity_id',
    'successor_entity_id',
    'verification_status',
    'confidence',
    'display_priority',
    'icon_class',
    'created_by',
    'date_method',
    'date_confidence',
    'duration_type',
    'location_confidence',
    'location_method',
    'source_citations',
    'primary_geo_ref_id',
])]
class Entity extends Model
{
    use HasFactory, HasNeighbors;

    protected $table = 'entities';

    protected $primaryKey = 'entity_id';

    public $incrementing = false;

    protected $keyType = 'string';

    /**
     * Columns hidden from serialization by default.
     * The embedding vector is ~12 KB/row and only needed for similarity search.
     *
     * @var list<string>
     */
    protected $hidden = [
        'embedding',
    ];

    /**
     * Get the attributes that should be cast.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'entity_type' => EntityType::class,
            'entity_group' => EntityGroup::class,
            'verification_status' => VerificationStatus::class,
            'confidence' => ConfidenceLevel::class,
            'location_confidence' => ConfidenceLevel::class,
            'date_confidence' => ConfidenceLevel::class,
            'date_method' => DateResolutionMethod::class,
            'duration_type' => DurationType::class,
            'location_method' => LocationResolutionMethod::class,
            'icon_class' => IconClass::class,
            'geom' => GeoJson::class,
            'territory_geom' => GeoJson::class,
            'embedding' => Vector::class,
            'attributes' => 'json',
            'source_citations' => 'json',
            'tags' => PgTextArray::class,
            'alternative_names' => PgTextArray::class,
            'review_date' => 'datetime',
        ];
    }

    // ── Relationships ────────────────────────────────────────

    /** @return BelongsTo<Entity, $this> */
    public function parent(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'parent_entity_id', 'entity_id');
    }

    /** @return HasMany<Entity, $this> */
    public function children(): HasMany
    {
        return $this->hasMany(Entity::class, 'parent_entity_id', 'entity_id');
    }

    /** @return BelongsTo<Entity, $this> */
    public function successor(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'successor_entity_id', 'entity_id');
    }

    /** @return HasOne<Entity, $this> */
    public function predecessor(): HasOne
    {
        return $this->hasOne(Entity::class, 'successor_entity_id', 'entity_id');
    }

    /** @return BelongsTo<User, $this> */
    public function reviewer(): BelongsTo
    {
        return $this->belongsTo(User::class, 'reviewer_id');
    }

    /** @return HasMany<EntityGeoRef, $this> */
    public function geoRefs(): HasMany
    {
        return $this->hasMany(EntityGeoRef::class, 'entity_id', 'entity_id')
            ->orderByDesc('is_active')
            ->orderByRaw("CASE WHEN match_role = 'primary' THEN 0 ELSE 1 END")
            ->orderByDesc('match_score');
    }

    /** @return BelongsTo<EntityGeoRef, $this> */
    public function primaryGeoRef(): BelongsTo
    {
        return $this->belongsTo(EntityGeoRef::class, 'primary_geo_ref_id', 'geo_ref_id');
    }

    /** @return HasMany<EntityRelationship, $this> */
    public function outgoingRelationships(): HasMany
    {
        return $this->hasMany(EntityRelationship::class, 'source_entity_id', 'entity_id');
    }

    /** @return HasMany<EntityRelationship, $this> */
    public function incomingRelationships(): HasMany
    {
        return $this->hasMany(EntityRelationship::class, 'target_entity_id', 'entity_id');
    }

    // ── Custom Query Builder ─────────────────────────────────

    /**
     * Create a new Eloquent query builder for the model.
     *
     * @param  Builder  $query
     * @return EntityBuilder<static>
     */
    public function newEloquentBuilder($query): EntityBuilder
    {
        return new EntityBuilder($query);
    }
}
