<?php

declare(strict_types=1);

namespace Database\Seeders;

use Database\Seeders\Traits\PgArrayLiteral;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;

class WritingSystemSeeder extends Seeder
{
    use PgArrayLiteral;

    public function run(): void
    {
        $table = 'ref_writing_systems';

        // Disable FK checks for self-referencing derived_from
        DB::statement('ALTER TABLE ref_writing_systems DISABLE TRIGGER ALL');
        DB::table($table)->truncate();

        $systems = $this->buildWritingSystems();
        foreach ($systems as $system) {
            DB::table($table)->insert($system);
        }

        DB::statement('ALTER TABLE ref_writing_systems ENABLE TRIGGER ALL');
    }

    /**
     * @return array<int, array<string, mixed>>
     */
    private function buildWritingSystems(): array
    {
        return [
            // ID 1: Egyptian hieroglyphs — no parent
            [
                'system_id' => 1,
                'name' => 'Egyptian hieroglyphs',
                'code' => 'Egyp',
                'system_type' => 'mixed',
                'direction' => 'variable',
                'origin_date' => '-3200~',
                'origin_location' => 'Egypt',
                'derived_from' => null,
                'languages_using' => $this->textArray(['Ancient Egyptian']),
                'still_in_use' => false,
                'unicode_block' => 'Egyptian Hieroglyphs',
                'ocr_support_level' => 'poor',
            ],
            // ID 2: Cuneiform — no parent (proto-cuneiform origin)
            [
                'system_id' => 2,
                'name' => 'Cuneiform',
                'code' => 'Xsux',
                'system_type' => 'mixed',
                'direction' => 'ltr',
                'origin_date' => '-3400~',
                'origin_location' => 'Mesopotamia',
                'derived_from' => null,
                'languages_using' => $this->textArray(['Sumerian', 'Akkadian', 'Hittite', 'Elamite', 'Hurrian']),
                'still_in_use' => false,
                'unicode_block' => 'Cuneiform',
                'ocr_support_level' => 'poor',
            ],
            // ID 3: Proto-Sinaitic — derived from Egyptian hieroglyphs (1)
            [
                'system_id' => 3,
                'name' => 'Proto-Sinaitic',
                'code' => null,
                'system_type' => 'abjad',
                'direction' => 'ltr',
                'origin_date' => '-1800~',
                'origin_location' => 'Sinai Peninsula',
                'derived_from' => 1,
                'languages_using' => $this->textArray(['Proto-Canaanite']),
                'still_in_use' => false,
                'unicode_block' => null,
                'ocr_support_level' => 'none',
            ],
            // ID 4: Phoenician — derived from Proto-Sinaitic (3)
            [
                'system_id' => 4,
                'name' => 'Phoenician',
                'code' => 'Phnx',
                'system_type' => 'abjad',
                'direction' => 'rtl',
                'origin_date' => '-1050~',
                'origin_location' => 'Byblos, Phoenicia',
                'derived_from' => 3,
                'languages_using' => $this->textArray(['Phoenician', 'Punic']),
                'still_in_use' => false,
                'unicode_block' => 'Phoenician',
                'ocr_support_level' => 'poor',
            ],
            // ID 5: Greek — derived from Phoenician (4)
            [
                'system_id' => 5,
                'name' => 'Greek',
                'code' => 'Grek',
                'system_type' => 'alphabet',
                'direction' => 'ltr',
                'origin_date' => '-800~',
                'origin_location' => 'Greece',
                'derived_from' => 4,
                'languages_using' => $this->textArray(['Greek']),
                'still_in_use' => true,
                'unicode_block' => 'Greek and Coptic',
                'ocr_support_level' => 'excellent',
            ],
            // ID 6: Latin — derived from Greek via Etruscan (5)
            [
                'system_id' => 6,
                'name' => 'Latin',
                'code' => 'Latn',
                'system_type' => 'alphabet',
                'direction' => 'ltr',
                'origin_date' => '-700~',
                'origin_location' => 'Italy',
                'derived_from' => 5,
                'languages_using' => $this->textArray(['Latin', 'English', 'French', 'Spanish', 'Portuguese', 'Italian', 'German', 'Turkish']),
                'still_in_use' => true,
                'unicode_block' => 'Basic Latin',
                'ocr_support_level' => 'excellent',
            ],
            // ID 7: Cyrillic — derived from Greek (5)
            [
                'system_id' => 7,
                'name' => 'Cyrillic',
                'code' => 'Cyrl',
                'system_type' => 'alphabet',
                'direction' => 'ltr',
                'origin_date' => '893',
                'origin_location' => 'Bulgaria',
                'derived_from' => 5,
                'languages_using' => $this->textArray(['Russian', 'Ukrainian', 'Bulgarian', 'Serbian', 'Belarusian']),
                'still_in_use' => true,
                'unicode_block' => 'Cyrillic',
                'ocr_support_level' => 'excellent',
            ],
            // ID 8: Arabic — derived from Phoenician lineage (Nabataean → Aramaic → Phoenician)
            // Simplifying: derived_from Phoenician (4) as the ancestral abjad
            [
                'system_id' => 8,
                'name' => 'Arabic',
                'code' => 'Arab',
                'system_type' => 'abjad',
                'direction' => 'rtl',
                'origin_date' => '400~',
                'origin_location' => 'Arabia',
                'derived_from' => 4,
                'languages_using' => $this->textArray(['Arabic', 'Persian', 'Urdu', 'Pashto', 'Malay (historical)']),
                'still_in_use' => true,
                'unicode_block' => 'Arabic',
                'ocr_support_level' => 'good',
            ],
            // ID 9: Hebrew — derived from Phoenician lineage (via Aramaic)
            [
                'system_id' => 9,
                'name' => 'Hebrew',
                'code' => 'Hebr',
                'system_type' => 'abjad',
                'direction' => 'rtl',
                'origin_date' => '-200~',
                'origin_location' => 'Levant',
                'derived_from' => 4,
                'languages_using' => $this->textArray(['Hebrew', 'Yiddish', 'Ladino']),
                'still_in_use' => true,
                'unicode_block' => 'Hebrew',
                'ocr_support_level' => 'good',
            ],
            // ID 10: Devanagari — derived from Brahmi (not in list; use null as Brahmi is ancestor)
            [
                'system_id' => 10,
                'name' => 'Devanagari',
                'code' => 'Deva',
                'system_type' => 'abugida',
                'direction' => 'ltr',
                'origin_date' => '700~',
                'origin_location' => 'India',
                'derived_from' => null,
                'languages_using' => $this->textArray(['Hindi', 'Sanskrit', 'Marathi', 'Nepali']),
                'still_in_use' => true,
                'unicode_block' => 'Devanagari',
                'ocr_support_level' => 'good',
            ],
            // ID 11: Chinese characters — no parent (oracle bone script origin)
            [
                'system_id' => 11,
                'name' => 'Chinese characters',
                'code' => 'Hani',
                'system_type' => 'logographic',
                'direction' => 'ttb',
                'origin_date' => '-1200~',
                'origin_location' => 'China',
                'derived_from' => null,
                'languages_using' => $this->textArray(['Chinese (Mandarin)', 'Chinese (Cantonese)', 'Japanese (Kanji)', 'Korean (historical)']),
                'still_in_use' => true,
                'unicode_block' => 'CJK Unified Ideographs',
                'ocr_support_level' => 'good',
            ],
            // ID 12: Linear B — derived from Linear A (not in list; use null)
            [
                'system_id' => 12,
                'name' => 'Linear B',
                'code' => 'Linb',
                'system_type' => 'syllabary',
                'direction' => 'ltr',
                'origin_date' => '-1450~',
                'origin_location' => 'Crete',
                'derived_from' => null,
                'languages_using' => $this->textArray(['Mycenaean Greek']),
                'still_in_use' => false,
                'unicode_block' => 'Linear B Syllabary',
                'ocr_support_level' => 'poor',
            ],
            // ID 13: Rongorongo — undeciphered; no known parent
            [
                'system_id' => 13,
                'name' => 'Rongorongo',
                'code' => 'Roro',
                'system_type' => 'undeciphered',
                'direction' => 'boustrophedon',
                'origin_date' => '1700~',
                'origin_location' => 'Easter Island',
                'derived_from' => null,
                'languages_using' => $this->textArray(['Rapa Nui (presumed)']),
                'still_in_use' => false,
                'unicode_block' => null,
                'ocr_support_level' => 'none',
            ],
        ];
    }
}
