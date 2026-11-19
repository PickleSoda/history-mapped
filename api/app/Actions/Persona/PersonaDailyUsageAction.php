<?php

declare(strict_types=1);

namespace App\Actions\Persona;

use App\Models\PersonaMessage;
use App\Models\User;

/** How many messages a user has sent today (UTC) against the daily cap. */
class PersonaDailyUsageAction
{
    /** @return array{limit: int, used: int, remaining: int, resets_at: string} */
    public function __invoke(User $user): array
    {
        $limit = (int) config('persona.limits.daily_messages', 100);
        $dayStart = now()->utc()->startOfDay();
        $used = PersonaMessage::query()
            ->where('user_id', $user->id)
            ->where('role', 'user')
            ->where('created_at', '>=', $dayStart)
            ->count();

        return [
            'limit' => $limit,
            'used' => $used,
            'remaining' => max(0, $limit - $used),
            'resets_at' => $dayStart->addDay()->toIso8601String(),
        ];
    }
}
