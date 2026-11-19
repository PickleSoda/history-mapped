<?php

declare(strict_types=1);

namespace App\Actions\Persona;

use App\Models\PersonaConversation;
use App\Models\User;
use Illuminate\Support\Collection;

/** The people a user has talked with, most recent first (at most 100). */
class ListPersonaConversationsAction
{
    /** @return Collection<int, PersonaConversation> */
    public function __invoke(User $user): Collection
    {
        return PersonaConversation::query()
            ->where('user_id', $user->id)
            ->whereNotNull('last_message_at')
            ->with([
                'entity:entity_id,name,entity_type,attributes',
                'entity.primaryTemporalRange',
                'latestMessage:id,conversation_id,role,content,created_at',
            ])
            ->orderByDesc('last_message_at')
            ->limit(100)
            ->get();
    }
}
