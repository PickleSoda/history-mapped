<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class SourceTypeDefinition extends Model
{
    protected $table = 'ref_source_type_definitions';

    protected $primaryKey = 'definition_id';

    public $timestamps = false;

    protected $guarded = [];

    /**
     * Get the attributes that should be cast.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'examples' => 'array',
            'requires_corroboration' => 'boolean',
            'weight_in_scoring' => 'decimal:2',
        ];
    }
}
