<?php

declare(strict_types=1);

namespace App\Models;

use App\Casts\GeoJson;
use App\Enums\ConfidenceLevel;
use App\Enums\DateResolutionMethod;
use App\Enums\DurationType;
use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Enums\IconClass;
use App\Enums\LocationResolutionMethod;
use App\Enums\VerificationStatus;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;
use Pgvector\Laravel\HasNeighbors;

#[Fillable([
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
    'date_raw',
    'location_name',
    'parent_entity_id',
    'successor_entity_id',
    'verification_status',
    'confidence',
    'display_priority',
    'icon_class',
    'entity_color',
    'created_by',
    'embedding_version',
    'confidence_notes',
    'date_method',
    'date_confidence',
    'duration_type',
    'location_confidence',
    'location_method',
    'validation_flags',
    'source_citations',
    'media_refs',
    'confidence_breakdown',
    'relationship_summary',
    'source_diversity_score',
    'temporal_display_range',
    'nearby_entity_count',
    'cluster_id',
    'era_label',
])]
class Entity extends Model
{
    use HasFactory, HasNeighbors;

    protected $table = 'entities';

    protected $primaryKey = 'entity_id';

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
            'embedding' => \Pgvector\Laravel\Vector::class,
            'attributes' => 'json',
            'source_citations' => 'json',
            'media_refs' => 'json',
            'confidence_breakdown' => 'json',
            'relationship_summary' => 'json',
            'tags' => 'array',
            'alternative_names' => 'array',
            'validation_flags' => 'array',
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

    // ── Scopes ───────────────────────────────────────────────

    /** @param Builder<Entity> $query */
    public function scopeOfType(Builder $query, EntityType $type): void
    {
        $query->where('entity_type', $type);
    }

    /** @param Builder<Entity> $query */
    public function scopeOfGroup(Builder $query, EntityGroup $group): void
    {
        $query->where('entity_group', $group);
    }

    /** @param Builder<Entity> $query */
    public function scopeVerified(Builder $query): void
    {
        $query->whereIn('verification_status', [
            VerificationStatus::HumanVerified,
            VerificationStatus::ExpertVerified,
        ]);
    }

    /** @param Builder<Entity> $query */
    public function scopeInBbox(Builder $query, float $minLng, float $minLat, float $maxLng, float $maxLat): void
    {
        $query->whereRaw(
            'ST_Intersects(geom, ST_MakeEnvelope(?, ?, ?, ?, 4326))',
            [$minLng, $minLat, $maxLng, $maxLat],
        );
    }

    /** @param Builder<Entity> $query */
    public function scopeInTimeRange(Builder $query, string $start, string $end): void
    {
        $query->where('temporal_start', '<=', $end)
            ->where('temporal_end', '>=', $start);
    }
}
