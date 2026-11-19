<?php

declare(strict_types=1);

namespace App\Support;

use Closure;
use Illuminate\Support\Facades\DB;

/**
 * Run one query with Postgres settings changed for it alone, such as a
 * planner switch (`enable_mergejoin`) or pg_trgm's similarity threshold.
 */
final class PgSettings
{
    /**
     * set_config(…, true) lasts to the end of the transaction; the RESET puts
     * the default back at once for a caller already inside one (a test, say),
     * where this transaction is only a savepoint.
     *
     * @template T
     *
     * @param  array<string, string>  $settings
     * @param  Closure(): T  $query
     * @return T
     */
    public static function with(array $settings, Closure $query): mixed
    {
        return DB::transaction(function () use ($settings, $query): mixed {
            foreach ($settings as $name => $value) {
                DB::select('SELECT set_config(?, ?, true)', [$name, $value]);
            }
            $result = $query();
            foreach (array_keys($settings) as $name) {
                DB::statement("RESET {$name}");
            }

            return $result;
        });
    }
}
