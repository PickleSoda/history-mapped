<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Actions\Discover\BuildAnniversariesAction;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;

/**
 * Rebuild `discover_anniversaries`, what GET /discover/on-this-day reads:
 * every entity whose dates have a real day, by month and day
 * (BuildAnniversariesAction has the rules).
 *
 *   php artisan discover:build-anniversaries
 *   php artisan discover:build-anniversaries --if-empty
 *
 * Idempotent: it replaces the table in one transaction and forgets the cached
 * days. It reads every person's attributes (about 3 s locally, tens of
 * seconds on the droplet), so the scheduler runs it weekly.
 *
 * `--if-empty` does nothing when the table has rows. The scheduler runs that
 * form hourly: a first deploy, or a content load (which empties the table
 * with the entities it truncates), is followed by a build within the hour
 * without anyone running it by hand.
 */
class BuildDiscoverAnniversariesCommand extends Command
{
    protected $signature = 'discover:build-anniversaries
        {--if-empty : Do nothing when the table already has rows}';

    protected $description = 'Rebuild the "on this day" table from the dates that have a real day';

    public function handle(BuildAnniversariesAction $build): int
    {
        if ($this->option('if-empty') && DB::table('discover_anniversaries')->exists()) {
            $this->components->info('The anniversaries are already built.');

            return self::SUCCESS;
        }

        $started = microtime(true);
        $built = $build();

        $this->components->twoColumnDetail(
            'Anniversaries rebuilt',
            sprintf('%s rows in %.1f s', number_format($built['rows']), microtime(true) - $started),
        );
        $this->components->twoColumnDetail('From date ranges', number_format($built['from_ranges']));
        $this->components->twoColumnDetail("From people's birth and death dates", number_format($built['from_people']));
        $this->components->twoColumnDetail(
            'Days of the year covered',
            sprintf('%d of 366 (fewest %d on a day, median %d)', $built['days'], $built['fewest'], $built['median']),
        );

        return self::SUCCESS;
    }
}
