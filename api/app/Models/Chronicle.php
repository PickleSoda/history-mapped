<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\ChronicleStatus;
use App\Enums\SourceType;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

#[Fillable([
    'chronicle_id', 'title', 'slug', 'source_type', 'source_reference',
    'status', 'start_year', 'end_year', 'impact_score', 'approximate_location', 'metadata', 'created_by', 'created_at', 'updated_at',
])]
class Chronicle extends Model
{
    use HasFactory;

    protected $table = 'chronicles';
    protected $primaryKey = 'chronicle_id';
    public $incrementing = false;
    protected $keyType = 'string';

    protected function casts(): array
    {
        return [
            'status' => ChronicleStatus::class,
            'source_type' => SourceType::class,
            'start_year' => 'integer',
            'end_year' => 'integer',
            'impact_score' => 'integer',
            'approximate_location' => 'json',
            'metadata' => 'json',
        ];
    }

    /** @return HasMany<ChronicleEntry, $this> */
    public function entries(): HasMany
    {
        return $this->hasMany(ChronicleEntry::class, 'chronicle_id', 'chronicle_id')
            ->orderBy('sequence_order');
    }
}
