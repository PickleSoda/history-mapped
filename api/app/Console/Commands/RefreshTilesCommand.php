<?php

declare(strict_types=1);

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;

/**
 * Refresh `tiles.atlas_features`, the precomputed table the atlas tiles are
 * cut from (migration 2026_11_18_000001, docs/schemas/atlas-tiles.md).
 *
 *   php artisan tiles:refresh           # only when the content changed
 *   php artisan tiles:refresh --force   # always (after a content load)
 *
 * Statement triggers on geometry_periods, entities, entity_aliases,
 * entity_geo_refs and map_stories bump `tiles.change_seq`. The command
 * remembers the value it last refreshed at and does nothing while the value
 * stands still. The refresh runs CONCURRENTLY, so tiles keep serving.
 */
class RefreshTilesCommand extends Command
{
    public const CACHE_KEY = 'tiles:refreshed-at-change';

    protected $signature = 'tiles:refresh
        {--force : Refresh even when nothing changed since the last refresh}';

    protected $description = 'Refresh the precomputed atlas tile features when the content changed';

    public function handle(): int
    {
        // Read before refreshing: a change that lands during the refresh moves
        // the counter past this value, so the next run refreshes again.
        $change = (int) DB::selectOne('SELECT last_value FROM tiles.change_seq')->last_value;

        // The Redis store hands numbers back as strings, so compare as integers.
        $refreshedAt = Cache::get(self::CACHE_KEY);
        if (! $this->option('force') && is_numeric($refreshedAt) && (int) $refreshedAt === $change) {
            $this->components->info('Atlas tile features are current.');

            return self::SUCCESS;
        }

        $started = microtime(true);
        DB::statement('REFRESH MATERIALIZED VIEW CONCURRENTLY tiles.atlas_features');
        Cache::forever(self::CACHE_KEY, $change);

        $this->components->twoColumnDetail(
            'Atlas tile features refreshed',
            sprintf('%s rows in %.1f s', number_format((int) DB::selectOne('SELECT count(*) AS n FROM tiles.atlas_features')->n), microtime(true) - $started),
        );

        return self::SUCCESS;
    }
}
