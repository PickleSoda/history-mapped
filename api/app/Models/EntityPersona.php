<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * The generated character sheet of one speaker (see config/persona.php).
 *
 * `persona` keys: voice, temperament[], values[], speech_habits[], cares_about[],
 * address_to_acquaintance, language_note, self_view.
 */
#[Fillable(['entity_id', 'persona', 'knowledge_year', 'model', 'version', 'source'])]
class EntityPersona extends Model
{
    protected function casts(): array
    {
        return ['persona' => 'array', 'knowledge_year' => 'integer', 'version' => 'integer'];
    }

    /** @return BelongsTo<Entity, $this> */
    public function entity(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'entity_id', 'entity_id');
    }
}
