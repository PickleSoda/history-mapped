<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

/**
 * A `chronicle_entry_entities` row (entry_id, entity_id, role, sequence_in_entry). Read-only row model
 * so the content-bundle export reads the links without hydrating `Entity` models.
 */
class ChronicleEntryEntity extends Model
{
    protected $table = 'chronicle_entry_entities';

    protected $primaryKey = null;

    public $incrementing = false;

    public $timestamps = false;
}
