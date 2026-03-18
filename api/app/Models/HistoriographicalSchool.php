<?php

declare(strict_types=1);

namespace App\Models;

use App\Casts\PgIntArray;
use App\Casts\PgTextArray;
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
            'alternative_names' => PgTextArray::class,
            'dominant_regions' => PgTextArray::class,
            'dominant_periods' => PgTextArray::class,
            'key_historians' => PgTextArray::class,
            'foundational_works' => PgTextArray::class,
            'influenced_by' => PgIntArray::class,
            'opposed_to' => PgIntArray::class,
        ];
    }
}
