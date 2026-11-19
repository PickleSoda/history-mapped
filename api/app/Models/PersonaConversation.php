<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;

/** One user's single conversation with one speaker. */
#[Fillable(['user_id', 'entity_id', 'last_message_at', 'summary', 'summarised_until_id'])]
class PersonaConversation extends Model
{
    protected function casts(): array
    {
        return ['last_message_at' => 'datetime', 'summarised_until_id' => 'integer'];
    }

    /** @return BelongsTo<User, $this> */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /** @return BelongsTo<Entity, $this> */
    public function entity(): BelongsTo
    {
        return $this->belongsTo(Entity::class, 'entity_id', 'entity_id');
    }

    /** @return HasMany<PersonaMessage, $this> */
    public function messages(): HasMany
    {
        return $this->hasMany(PersonaMessage::class, 'conversation_id')->orderBy('id');
    }

    /** @return HasOne<PersonaMessage, $this> */
    public function latestMessage(): HasOne
    {
        return $this->hasOne(PersonaMessage::class, 'conversation_id')->latestOfMany('id');
    }
}
