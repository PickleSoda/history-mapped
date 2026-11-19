<?php

declare(strict_types=1);

namespace App\Actions\Persona;

use App\Models\Entity;
use App\Models\PersonaConversation;
use App\Models\User;

/** Delete a user's conversation with one person (messages cascade). Idempotent. */
class ClearPersonaConversationAction
{
    public function __invoke(User $user, Entity $entity): void
    {
        PersonaConversation::where('user_id', $user->id)->where('entity_id', $entity->entity_id)->delete();
    }
}
