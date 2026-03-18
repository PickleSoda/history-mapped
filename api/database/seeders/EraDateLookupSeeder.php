<?php

declare(strict_types=1);

namespace Database\Seeders;

use Database\Seeders\Traits\PgArrayLiteral;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;

class EraDateLookupSeeder extends Seeder
{
    use PgArrayLiteral;

    public function run(): void
    {
        $table = 'ref_era_date_lookup';

        DB::table($table)->truncate();

        $lookups = [
            [
                'lookup_id' => 1,
                'search_term' => 'late bronze age',
                'search_variants' => $this->textArray(['lba', 'bronze age collapse']),
                'resolved_start' => '-1600',
                'resolved_end' => '-1200',
                'geographic_scope' => 'Eastern Mediterranean',
                'confidence' => 'medium-low',
                'notes' => 'Exact dates debated; some scholars use -1150 for end',
                'period_id' => 9,
            ],
            [
                'lookup_id' => 2,
                'search_term' => 'hellenistic period',
                'search_variants' => $this->textArray(['hellenistic age', 'hellenistic era']),
                'resolved_start' => '-323',
                'resolved_end' => '-31',
                'geographic_scope' => 'Mediterranean',
                'confidence' => 'medium-low',
                'notes' => null,
                'period_id' => 14,
            ],
            [
                'lookup_id' => 3,
                'search_term' => 'roman republic',
                'search_variants' => $this->textArray(['republican rome', 'republican period']),
                'resolved_start' => '-509',
                'resolved_end' => '-27',
                'geographic_scope' => 'Mediterranean',
                'confidence' => 'medium-low',
                'notes' => null,
                'period_id' => 15,
            ],
            [
                'lookup_id' => 4,
                'search_term' => 'pax romana',
                'search_variants' => $this->textArray(['roman peace']),
                'resolved_start' => '-27',
                'resolved_end' => '180',
                'geographic_scope' => 'Mediterranean',
                'confidence' => 'medium-low',
                'notes' => 'Conventionally from Augustus to death of Marcus Aurelius',
                'period_id' => 20,
            ],
            [
                'lookup_id' => 5,
                'search_term' => 'crisis of the third century',
                'search_variants' => $this->textArray(['3rd century crisis', 'military anarchy']),
                'resolved_start' => '235',
                'resolved_end' => '284',
                'geographic_scope' => 'Roman Empire',
                'confidence' => 'medium-low',
                'notes' => null,
                'period_id' => 21,
            ],
            [
                'lookup_id' => 6,
                'search_term' => 'migration period',
                'search_variants' => $this->textArray(['völkerwanderung', 'barbarian invasions']),
                'resolved_start' => '375',
                'resolved_end' => '568',
                'geographic_scope' => 'Europe',
                'confidence' => 'medium-low',
                'notes' => 'Start often dated to Hunnic incursion; end varies by region',
                'period_id' => null,
            ],
            [
                'lookup_id' => 7,
                'search_term' => 'viking age',
                'search_variants' => $this->textArray(['norse expansion']),
                'resolved_start' => '793',
                'resolved_end' => '1066',
                'geographic_scope' => 'Northern Europe',
                'confidence' => 'medium-low',
                'notes' => 'Start: raid on Lindisfarne; end: Battle of Stamford Bridge',
                'period_id' => null,
            ],
            [
                'lookup_id' => 8,
                'search_term' => 'tang dynasty',
                'search_variants' => $this->textArray(['tang period']),
                'resolved_start' => '618',
                'resolved_end' => '907',
                'geographic_scope' => 'China',
                'confidence' => 'medium-low',
                'notes' => null,
                'period_id' => null,
            ],
            [
                'lookup_id' => 9,
                'search_term' => 'abbasid golden age',
                'search_variants' => $this->textArray(['islamic golden age']),
                'resolved_start' => '750',
                'resolved_end' => '1258',
                'geographic_scope' => 'Islamic world',
                'confidence' => 'medium-low',
                'notes' => 'Some scholars narrow "Golden Age" to 750-1000; full Abbasid range used here',
                'period_id' => 73,
            ],
            [
                'lookup_id' => 10,
                'search_term' => 'warring states',
                'search_variants' => $this->textArray(['warring states period']),
                'resolved_start' => '-476',
                'resolved_end' => '-221',
                'geographic_scope' => 'China',
                'confidence' => 'medium-low',
                'notes' => null,
                'period_id' => 56,
            ],
            [
                'lookup_id' => 11,
                'search_term' => 'meiji era',
                'search_variants' => $this->textArray(['meiji period', 'meiji restoration']),
                'resolved_start' => '1868',
                'resolved_end' => '1912',
                'geographic_scope' => 'Japan',
                'confidence' => 'medium-low',
                'notes' => null,
                'period_id' => null,
            ],
        ];

        foreach ($lookups as $lookup) {
            DB::table($table)->insert($lookup);
        }
    }
}
