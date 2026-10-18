<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

/**
 * A `chronicle_tags` row (chronicle_id, tag, source). Read-only row model so the content-bundle
 * export can eager-load tags with their `source`, which the `Chronicle::tags()` pivot does not expose.
 */
class ChronicleTag extends Model
{
    protected $table = 'chronicle_tags';

    protected $primaryKey = null;

    public $incrementing = false;

    public $timestamps = false;
}
