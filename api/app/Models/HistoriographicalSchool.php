<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class HistoriographicalSchool extends Model
{
    protected $table = 'ref_historiographical_schools';

    protected $primaryKey = 'school_id';

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
            'alternative_names' => 'array',
            'dominant_regions' => 'array',
            'dominant_periods' => 'array',
            'key_historians' => 'array',
            'foundational_works' => 'array',
            'influenced_by' => 'array',
            'opposed_to' => 'array',
        ];
    }
}
