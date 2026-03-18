<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\ReliabilityTier;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

#[Fillable([
    'title',
    'source_type',
    'document_type',
    'author',
    'date_created',
    'date_discovered',
    'language',
    'current_location',
    'source_url',
    'content_hash',
    'ingestion_date',
    'geographic_scope',
    'temporal_scope',
    'contemporaneity',
    'author_bias',
    'corroboration',
    'scholarly_consensus',
    'raw_file_path',
    'nlp_output_path',
    'llm_log_path',
])]
class Source extends Model
{
    use HasFactory;

    protected $table = 'sources';

    protected $primaryKey = 'source_id';

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
            'source_type' => ReliabilityTier::class,
            'ingestion_date' => 'datetime',
        ];
    }
}
