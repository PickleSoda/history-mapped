<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

#[Fillable([
    'entity_id',
    'name',
    'language',
    'source',
    'is_primary',
])]
class EntityAlias extends Model
{
    protected $table = 'entity_aliases';

    protected $primaryKey = 'alias_id';

    public $incrementing = false;

    protected $keyType = 'string';

    /** @return BelongsTo<Entity, $this> */
    public function entity(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'entity_id', 'entity_id');
    }
}
