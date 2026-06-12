<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;

#[Fillable([
    'entry_id', 'chronicle_id', 'sequence_order', 'start_year', 'end_year', 'impact_score', 'approximate_location',
    'primary_relationship_id', 'narrative_text', 'notes', 'source_evidence', 'generated_by',
])]
class ChronicleEntry extends Model
{
    use HasFactory;

    protected $table = 'chronicle_entries';
    protected $primaryKey = 'entry_id';
    public $incrementing = false;
    protected $keyType = 'string';

    protected function casts(): array
    {
        return [
            'sequence_order' => 'integer',
            'start_year' => 'integer',
            'end_year' => 'integer',
            'impact_score' => 'integer',
            'approximate_location' => 'json',
            'source_evidence' => 'array',
        ];
    }

    /** @return BelongsTo<Chronicle, $this> */
    public function chronicle(): BelongsTo
    {
        return $this->belongsTo(Chronicle::class, 'chronicle_id', 'chronicle_id');
    }

    /** @return BelongsTo<EntityRelationship, $this> */
    public function primaryRelationship(): BelongsTo
    {
        return $this->belongsTo(EntityRelationship::class, 'primary_relationship_id', 'relationship_id');
    }

    /** @return BelongsToMany<Entity, $this> */
    public function secondaryEntities(): BelongsToMany
    {
        return $this->belongsToMany(
            Entity::class,
            'chronicle_entry_entities',
            'entry_id',
            'entity_id',
        )->withPivot('role', 'sequence_in_entry');
    }

    public function getTimestampAttribute(): ?string
    {
        if ($this->relationLoaded('primaryRelationship') && $this->primaryRelationship?->temporal_start) {
            return $this->primaryRelationship->temporal_start;
        }

        if ($this->relationLoaded('secondaryEntities')) {
            foreach ($this->secondaryEntities as $entity) {
                if ($entity->relationLoaded('temporalRanges')) {
                    $earliest = $entity->temporalRanges
                        ->whereNotNull('start_year')
                        ->sortBy('start_year')
                        ->first();
                    if ($earliest) {
                        return (string) $earliest->start_year;
                    }
                }
            }
        }

        return null;
    }
}
