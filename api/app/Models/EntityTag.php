<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

#[Fillable([
    'entity_id',
    'tag',
])]
class EntityTag extends Model
{
    protected $table = 'entity_tags';

    protected $primaryKey = 'entity_tag_id';

    public $incrementing = false;

    protected $keyType = 'string';

    /** @return BelongsTo<Entity, $this> */
    public function entity(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'entity_id', 'entity_id');
    }
}
