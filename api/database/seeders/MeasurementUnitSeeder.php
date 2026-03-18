<?php

declare(strict_types=1);

namespace Database\Seeders;

use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;

class MeasurementUnitSeeder extends Seeder
{
    public function run(): void
    {
        $table = 'ref_measurement_units';

        DB::table($table)->truncate();

        $units = $this->buildUnits();
        $sort = 0;

        foreach ($units as $unit) {
            $unit['sort_order'] = ++$sort;
            DB::table($table)->insert($unit);
        }
    }

    /**
     * @return array<int, array<string, mixed>>
     */
    private function buildUnits(): array
    {
        return [
            [
                'unit_id' => 1,
                'name' => 'Roman mile',
                'symbol' => 'mille passuum',
                'measurement_type' => 'distance',
                'si_equivalent' => 1480,
                'si_unit' => 'm',
                'conversion_notes' => 'Defined as 1,000 double paces (passus). Varied slightly across provinces.',
                'used_by_region' => 'Roman Empire',
                'used_by_period' => 'Roman Republic and Empire (-509/476)',
                'approximate' => true,
            ],
            [
                'unit_id' => 2,
                'name' => 'Greek stadion',
                'symbol' => 'στάδιον',
                'measurement_type' => 'distance',
                'si_equivalent' => 185,
                'si_unit' => 'm',
                'conversion_notes' => 'Length of a typical Greek stadium. Varied by city-state: Attic ~185m, Olympic ~192m.',
                'used_by_region' => 'Classical Greece',
                'used_by_period' => 'Classical Antiquity (-800/300)',
                'approximate' => true,
            ],
            [
                'unit_id' => 3,
                'name' => 'Persian parasang',
                'symbol' => 'parasang',
                'measurement_type' => 'distance',
                'si_equivalent' => 5500,
                'si_unit' => 'm',
                'conversion_notes' => 'Originally the distance walked in one hour. Herodotus equated it to 30 stadia.',
                'used_by_region' => 'Achaemenid Empire',
                'used_by_period' => 'Achaemenid period (-550/-330)',
                'approximate' => true,
            ],
            [
                'unit_id' => 4,
                'name' => 'Chinese li',
                'symbol' => '里',
                'measurement_type' => 'distance',
                'si_equivalent' => 500,
                'si_unit' => 'm',
                'conversion_notes' => 'Varied considerably over Chinese history. Modern standardized li = 500m; historical values ranged from ~300m to ~576m.',
                'used_by_region' => 'Imperial China',
                'used_by_period' => 'Chinese dynastic period (-2070/1912)',
                'approximate' => true,
            ],
            [
                'unit_id' => 5,
                'name' => 'Roman foot',
                'symbol' => 'pes',
                'measurement_type' => 'distance',
                'si_equivalent' => 0.296,
                'si_unit' => 'm',
                'conversion_notes' => 'Base unit of Roman measurement. 5 pedes = 1 passus. Some scholars give 0.2957m.',
                'used_by_region' => 'Roman Empire',
                'used_by_period' => 'Roman Republic and Empire (-509/476)',
                'approximate' => true,
            ],
            [
                'unit_id' => 6,
                'name' => 'Egyptian royal cubit',
                'symbol' => 'meh niswt',
                'measurement_type' => 'distance',
                'si_equivalent' => 0.524,
                'si_unit' => 'm',
                'conversion_notes' => 'Royal cubit = 7 palms = 28 digits. Remarkably consistent across dynasties; the Turin cubit rod gives 0.5236m.',
                'used_by_region' => 'Ancient Egypt',
                'used_by_period' => 'Pharaonic Egypt (-3100/-30)',
                'approximate' => false,
            ],
            [
                'unit_id' => 7,
                'name' => 'Roman pound',
                'symbol' => 'libra',
                'measurement_type' => 'weight',
                'si_equivalent' => 327,
                'si_unit' => 'g',
                'conversion_notes' => '12 unciae = 1 libra. Source of the abbreviation "lb". Values range from 322g to 329g in scholarship.',
                'used_by_region' => 'Roman Empire',
                'used_by_period' => 'Roman Republic and Empire (-509/476)',
                'approximate' => true,
            ],
            [
                'unit_id' => 8,
                'name' => 'Greek talent (Attic)',
                'symbol' => 'τάλαντον',
                'measurement_type' => 'weight',
                'si_equivalent' => 26200,
                'si_unit' => 'g',
                'conversion_notes' => 'Attic talent = 60 minae = 6,000 drachmai. Other talent standards existed: Aeginetan ~37kg, Babylonian ~30kg.',
                'used_by_region' => 'Classical Greece',
                'used_by_period' => 'Classical Antiquity (-500/-31)',
                'approximate' => true,
            ],
            [
                'unit_id' => 9,
                'name' => 'Mesopotamian shekel',
                'symbol' => 'šiqlu',
                'measurement_type' => 'weight',
                'si_equivalent' => 8.3,
                'si_unit' => 'g',
                'conversion_notes' => 'Standard unit of weight and currency. 60 shekels = 1 mina. Varied between ~8.0g and ~8.5g across periods.',
                'used_by_region' => 'Mesopotamia',
                'used_by_period' => 'Mesopotamian civilizations (-3500/-539)',
                'approximate' => true,
            ],
            [
                'unit_id' => 10,
                'name' => 'Roman iugerum',
                'symbol' => 'iugerum',
                'measurement_type' => 'area',
                'si_equivalent' => 2523,
                'si_unit' => 'm2',
                'conversion_notes' => 'Area a yoke of oxen could plough in one day. 2 actus × 1 actus = 240 × 120 pedes.',
                'used_by_region' => 'Roman Empire',
                'used_by_period' => 'Roman Republic and Empire (-509/476)',
                'approximate' => true,
            ],
            [
                'unit_id' => 11,
                'name' => 'Chinese mu',
                'symbol' => '亩',
                'measurement_type' => 'area',
                'si_equivalent' => 614,
                'si_unit' => 'm2',
                'conversion_notes' => 'Traditional mu varied by dynasty. Modern mu = 666.67 m². Historical values ranged widely; 614 m² is a common estimate for Han-era mu.',
                'used_by_region' => 'Imperial China',
                'used_by_period' => 'Chinese dynastic period (-2070/1912)',
                'approximate' => true,
            ],
            [
                'unit_id' => 12,
                'name' => 'Roman amphora',
                'symbol' => 'amphora',
                'measurement_type' => 'volume',
                'si_equivalent' => 26.2,
                'si_unit' => 'L',
                'conversion_notes' => '1 amphora = 2 urnae = 8 congii = 48 sextarii. Standard unit for liquid trade goods (wine, olive oil).',
                'used_by_region' => 'Roman Empire',
                'used_by_period' => 'Roman Republic and Empire (-509/476)',
                'approximate' => true,
            ],
            [
                'unit_id' => 13,
                'name' => 'Modius',
                'symbol' => 'modius',
                'measurement_type' => 'volume',
                'si_equivalent' => 8.7,
                'si_unit' => 'L',
                'conversion_notes' => 'Roman dry measure for grain. 1 modius = 16 sextarii. Used in grain dole (annona) calculations.',
                'used_by_region' => 'Roman Empire',
                'used_by_period' => 'Roman Republic and Empire (-509/476)',
                'approximate' => true,
            ],
            [
                'unit_id' => 14,
                'name' => 'Artaba',
                'symbol' => 'artaba',
                'measurement_type' => 'volume',
                'si_equivalent' => 39,
                'si_unit' => 'L',
                'conversion_notes' => 'Egyptian/Persian grain measure. Herodotus gives 1 artaba ≈ 1 Attic medimnus. Ptolemaic standard ~39L.',
                'used_by_region' => 'Ptolemaic Egypt',
                'used_by_period' => 'Ptolemaic period (-305/-30)',
                'approximate' => true,
            ],
        ];
    }
}
