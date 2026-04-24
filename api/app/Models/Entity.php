<?php

declare(strict_types=1);

namespace App\Models;

use App\Builders\EntityBuilder;
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
    'impact_score',
    'wikidata_id',
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
            'embedding' => Vector::class,
            'attributes' => 'json',
            'source_citations' => 'json',
            'review_date' => 'datetime',
        ];
    }

    // ── Relationships ────────────────────────────────────────

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
    // ── V2 Entity Model Relations ─────────────────────────────────

    /** @return HasMany<EntityAlias, $this> */
    public function aliases(): HasMany
    {
        return $this->hasMany(EntityAlias::class, 'entity_id', 'entity_id');
    }

    /** @return HasMany<EntityTag, $this> */
    public function entityTags(): HasMany
    {
        return $this->hasMany(EntityTag::class, 'entity_id', 'entity_id');
    }

    /** @return HasMany<EntityTemporalRange, $this> */
    public function temporalRanges(): HasMany
    {
        return $this->hasMany(EntityTemporalRange::class, 'entity_id', 'entity_id');
    }

    /** @return HasMany<EntityLocation, $this> */
    public function locations(): HasMany
    {
        return $this->hasMany(EntityLocation::class, 'entity_id', 'entity_id');
    }

    /** @return HasOne<EntityTemporalRange, $this> */
    public function primaryTemporalRange(): HasOne
    {
        return $this->hasOne(EntityTemporalRange::class, 'entity_id', 'entity_id')
            ->where('is_primary', true)
            ->latest('updated_at');
    }

    /** @return HasOne<EntityLocation, $this> */
    public function primaryLocation(): HasOne
    {
        return $this->hasOne(EntityLocation::class, 'entity_id', 'entity_id')
            ->where('is_primary', true)
            ->latest('updated_at');
    }

    /** @return HasMany<GeometryPeriod, $this> */
    public function geometryPeriods(): HasMany
    {
        return $this->hasMany(GeometryPeriod::class, 'entity_id', 'entity_id');
    }

    /** @return HasMany<EntityTimelineEntry, $this> */
    public function timelineEntries(): HasMany
    {
        return $this->hasMany(EntityTimelineEntry::class, 'entity_id', 'entity_id');
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

    protected function getTemporalStartAttribute(): ?string
    {
        if (array_key_exists('temporal_start', $this->attributes)) {
            $value = $this->attributes['temporal_start'];

            return $value !== null ? (string) $value : null;
        }

        return $this->primaryTemporalRange?->start_date;
    }

    protected function getTemporalEndAttribute(): ?string
    {
        if (array_key_exists('temporal_end', $this->attributes)) {
            $value = $this->attributes['temporal_end'];

            return $value !== null ? (string) $value : null;
        }

        return $this->primaryTemporalRange?->end_date;
    }

    protected function getTemporalStartYearAttribute(): ?int
    {
        if (array_key_exists('temporal_start_year', $this->attributes)) {
            $value = $this->attributes['temporal_start_year'];

            return $value !== null ? (int) $value : null;
        }

        return $this->primaryTemporalRange?->start_year;
    }

    protected function getTemporalEndYearAttribute(): ?int
    {
        if (array_key_exists('temporal_end_year', $this->attributes)) {
            $value = $this->attributes['temporal_end_year'];

            return $value !== null ? (int) $value : null;
        }

        return $this->primaryTemporalRange?->end_year;
    }

    protected function getLocationNameAttribute(): ?string
    {
        if (array_key_exists('location_name', $this->attributes)) {
            $value = $this->attributes['location_name'];

            return $value !== null ? (string) $value : null;
        }

        return $this->primaryLocation?->location_name;
    }

    /** @return array<string, mixed>|null */
    protected function getGeomAttribute(): ?array
    {
        if (array_key_exists('geom', $this->attributes)) {
            $value = $this->attributes['geom'];

            return is_array($value) ? $value : null;
        }

        $geom = $this->primaryLocation?->geom;

        return is_array($geom) ? $geom : null;
    }

    /** @return array<string, mixed>|null */
    protected function getTerritoryGeomAttribute(): ?array
    {
        if (array_key_exists('territory_geom', $this->attributes)) {
            $value = $this->attributes['territory_geom'];

            return is_array($value) ? $value : null;
        }

        $territory = $this->primaryLocation?->territory_geom;

        return is_array($territory) ? $territory : null;
    }

    /** @return list<string> */
    protected function getTagsAttribute(): array
    {
        if (array_key_exists('tags', $this->attributes)) {
            $value = $this->attributes['tags'];

            return is_array($value) ? array_values($value) : [];
        }

        return $this->collectRelationValues('entityTags', 'tag');
    }

    /** @return list<string> */
    protected function getAlternativeNamesAttribute(): array
    {
        if (array_key_exists('alternative_names', $this->attributes)) {
            $value = $this->attributes['alternative_names'];

            return is_array($value) ? array_values($value) : [];
        }

        return $this->collectRelationValues('aliases', 'name');
    }

    /** @return list<string> */
    private function collectRelationValues(string $relationName, string $column): array
    {
        if ($this->relationLoaded($relationName)) {
            $relation = $this->getRelation($relationName);
            if (method_exists($relation, 'pluck')) {
                return array_values($relation->pluck($column)->filter()->map(
                    static fn (mixed $value): string => (string) $value,
                )->all());
            }
        }

        /** @var list<string> $values */
        $values = $this->{$relationName}()->pluck($column)->filter()->map(
            static fn (mixed $value): string => (string) $value,
        )->values()->all();

        return $values;
    }
}
