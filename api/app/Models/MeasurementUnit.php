<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class MeasurementUnit extends Model
{
    protected $table = 'ref_measurement_units';

    protected $primaryKey = 'unit_id';

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
            'approximate' => 'boolean',
            'si_equivalent' => 'decimal:6',
        ];
    }
}
