<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

#[Fillable(['conversation_id', 'user_id', 'role', 'content', 'model', 'prompt_tokens', 'completion_tokens'])]
class PersonaMessage extends Model
{
    public const UPDATED_AT = null;

    protected function casts(): array
    {
        return ['created_at' => 'datetime'];
    }

    /** @return BelongsTo<PersonaConversation, $this> */
    public function conversation(): BelongsTo
    {
        return $this->belongsTo(PersonaConversation::class, 'conversation_id');
    }
}
