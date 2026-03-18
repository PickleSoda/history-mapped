<?php

declare(strict_types=1);

namespace App\Models;

use App\Casts\PgTextArray;
use Illuminate\Database\Eloquent\Model;

class CalendarSystem extends Model
{
    protected $table = 'ref_calendar_systems';

    protected $primaryKey = 'calendar_id';

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
            'used_by_regions' => PgTextArray::class,
            'used_by_periods' => PgTextArray::class,
            'month_names' => 'json',
            'still_in_use' => 'boolean',
        ];
    }
}
