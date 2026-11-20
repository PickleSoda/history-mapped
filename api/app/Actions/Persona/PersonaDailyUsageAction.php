<?php

declare(strict_types=1);

namespace App\Actions\Persona;

use App\Models\User;
use Illuminate\Support\Facades\DB;

/**
 * A user's messages today (UTC) against the daily cap. Kept in a counter row
 * (`persona_daily_usage`), so cleared conversations still count, and taken
 * with one atomic statement, so parallel sends cannot pass the cap together.
 */
class PersonaDailyUsageAction
{
    /** @return array{limit: int, used: int, remaining: int, resets_at: string} */
    public function __invoke(User $user): array
    {
        $limit = $this->limit();
        $used = (int) DB::table('persona_daily_usage')
            ->where('user_id', $user->id)
            ->where('day', $this->day())
            ->value('used');

        return [
            'limit' => $limit,
            'used' => $used,
            'remaining' => max(0, $limit - $used),
            'resets_at' => now()->utc()->startOfDay()->addDay()->toIso8601String(),
        ];
    }

    /** Take one message from today's allowance; false when none is left. */
    public function reserve(User $user): bool
    {
        $limit = $this->limit();
        if ($limit <= 0) {
            return false;
        }

        return DB::select(
            'INSERT INTO persona_daily_usage (user_id, day, used) VALUES (?, ?, 1)
             ON CONFLICT (user_id, day) DO UPDATE SET used = persona_daily_usage.used + 1
             WHERE persona_daily_usage.used < ?
             RETURNING used',
            [$user->id, $this->day(), $limit],
        ) !== [];
    }

    /** Give a reserved message back (the reply could not be written). */
    public function release(User $user): void
    {
        DB::update(
            'UPDATE persona_daily_usage SET used = used - 1 WHERE user_id = ? AND day = ? AND used > 0',
            [$user->id, $this->day()],
        );
    }

    public function limit(): int
    {
        return (int) config('persona.limits.daily_messages', 100);
    }

    private function day(): string
    {
        return now()->utc()->toDateString();
    }
}
