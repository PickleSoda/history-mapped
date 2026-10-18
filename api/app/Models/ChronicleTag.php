<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

/**
 * A `chronicle_tags` row (chronicle_id, tag, source). Read-only row model for the content-bundle export,
 * which skips the join to `tags`, the `ordered()` sort and the `Tag` hydration of `Chronicle::tags()`.
 * Export-only: there is no key, so don't use collection key operations (unique/find/contains/modelKeys/fresh)
 * and don't queue it.
 */
class ChronicleTag extends Model
{
    protected $table = 'chronicle_tags';

    protected $primaryKey = null;

    public $incrementing = false;

    public $timestamps = false;
}
