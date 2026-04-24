<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\ConfidenceLevel;
use App\Enums\RelationshipType;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

#[Fillable([
    'relationship_id',
    'source_entity_id',
    'target_entity_id',
    'relationship_type',
    'temporal_start',
    'temporal_end',
    'start_year',
    'end_year',
    'description',
    'confidence',
    'source_citations',
    'created_by',
    'derive_geometry_period',
])]
class EntityRelationship extends Model
{
    use HasFactory;

    protected $table = 'relationships';

    protected $primaryKey = 'relationship_id';

    public $incrementing = false;

    protected $keyType = 'string';

    public const CREATED_AT = 'created_at';

    public const UPDATED_AT = null;

    /**
     * Get the attributes that should be cast.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'relationship_type' => RelationshipType::class,
            'confidence' => ConfidenceLevel::class,
            'source_citations' => 'json',
            'start_year' => 'integer',
            'end_year' => 'integer',
            'derive_geometry_period' => 'boolean',
        ];
    }

    // ── Relationships ────────────────────────────────────────

    /** @return BelongsTo<Entity, $this> */
    public function sourceEntity(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'source_entity_id', 'entity_id');
    }

    /** @return BelongsTo<Entity, $this> */
    public function targetEntity(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'target_entity_id', 'entity_id');
    }
}
