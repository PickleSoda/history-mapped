<?php

declare(strict_types=1);

namespace Database\Seeders;

use Illuminate\Database\Seeder;

class ReferenceTableSeeder extends Seeder
{
    /**
     * Seed all 10 reference tables in FK-dependency order.
     *
     * Order rationale:
     * 1. GeographicRegion — no FKs to other ref tables
     * 2. HistoricalPeriod — FK to geographic_regions (region_id), self-ref parent_period_id
     * 3. HistoriographicalSchool — no FKs, but influenced_by/opposed_to are int[] cross-refs within same table
     * 4. CalendarSystem — no FKs to other ref tables
     * 5. EraDateLookup — FK to historical_periods (period_id)
     * 6. WritingSystem — self-ref derived_from, no other ref-table FKs
     * 7. ReligiousTradition — self-ref parent_tradition_id, no other ref-table FKs
     * 8. MeasurementUnit — no FKs
     * 9. LanguageFamily — self-ref parent_family_id, no other ref-table FKs
     * 10. SourceTypeDefinition — no FKs
     */
    public function run(): void
    {
        $this->call([
            GeographicRegionSeeder::class,
            HistoricalPeriodSeeder::class,
            HistoriographicalSchoolSeeder::class,
            CalendarSystemSeeder::class,
            EraDateLookupSeeder::class,
            WritingSystemSeeder::class,
            ReligiousTraditionSeeder::class,
            MeasurementUnitSeeder::class,
            LanguageFamilySeeder::class,
            SourceTypeDefinitionSeeder::class,
        ]);
    }
}
