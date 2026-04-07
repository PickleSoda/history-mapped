<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\ConfidenceLevel;
use App\Enums\DateResolutionMethod;
use App\Enums\DurationType;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

#[Fillable([
    'entity_id',
    'range_type',
    'start_year',
    'end_year',
    'start_date',
    'end_date',
    'duration_type',
    'date_method',
    'date_confidence',
    'is_primary',
    'notes',
])]
class EntityTemporalRange extends Model
{
    protected $table = 'entity_temporal_ranges';

    protected $primaryKey = 'temporal_range_id';

    public $incrementing = false;

    protected $keyType = 'string';

    protected function casts(): array
    {
        return [
            'duration_type' => DurationType::class,
            'date_method' => DateResolutionMethod::class,
            'date_confidence' => ConfidenceLevel::class,
            'is_primary' => 'boolean',
        ];
    }

    /** @return BelongsTo<Entity, $this> */
    public function entity(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'entity_id', 'entity_id');
    }
}
