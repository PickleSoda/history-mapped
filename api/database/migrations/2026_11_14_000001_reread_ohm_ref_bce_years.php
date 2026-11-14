<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * Re-read the BCE years of OHM geography references.
 *
 * OHM writes dates in ISO 8601 astronomical numbering (0000 is 1 BCE, -0043 is
 * 44 BCE), but the importers stored the year as written, so every ref with a
 * year of 0 or less sits one year late in our numbering (no year 0, -44 is
 * 44 BCE). OhmDate::yearFromDate now converts; this moves the stored years the
 * same way.
 *
 * Only a year that is still the as-written reading of its raw date string
 * moves, so an edited year stays put and running this twice changes nothing.
 * Geometry periods are left alone: the imports that write them take the
 * entity's own years.
 */
return new class extends Migration
{
    private const DATE = '^\\s*-?\\d{1,6}(-\\d{2}(-\\d{2})?)?\\s*$';

    private const YEAR = '^\\s*(-?\\d{1,6})';

    public function up(): void
    {
        foreach (['start', 'end'] as $bound) {
            DB::update(
                "UPDATE entity_geo_refs
                 SET temporal_{$bound}_year = temporal_{$bound}_year - 1
                 WHERE provider = 'ohm'
                   AND temporal_{$bound}_year <= 0
                   AND temporal_{$bound} ~ ?
                   AND temporal_{$bound}_year = substring(temporal_{$bound} from CAST(? AS text))::int",
                [self::DATE, self::YEAR],
            );
        }
    }

    public function down(): void
    {
        foreach (['start', 'end'] as $bound) {
            DB::update(
                "UPDATE entity_geo_refs
                 SET temporal_{$bound}_year = temporal_{$bound}_year + 1
                 WHERE provider = 'ohm'
                   AND temporal_{$bound}_year < 0
                   AND temporal_{$bound} ~ ?
                   AND temporal_{$bound}_year = substring(temporal_{$bound} from CAST(? AS text))::int - 1",
                [self::DATE, self::YEAR],
            );
        }
    }
};
