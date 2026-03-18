<?php

declare(strict_types=1);

namespace Database\Seeders;

use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;

class LanguageFamilySeeder extends Seeder
{
    public function run(): void
    {
        $table = 'ref_language_families';

        // Disable FK checks for self-referencing parent_family_id
        DB::statement('ALTER TABLE ref_language_families DISABLE TRIGGER ALL');
        DB::table($table)->truncate();

        $families = $this->buildFamilyTree();
        $sort = 0;

        foreach ($families as $family) {
            $family['sort_order'] = ++$sort;
            DB::table($table)->insert($family);
        }

        DB::statement('ALTER TABLE ref_language_families ENABLE TRIGGER ALL');
    }

    /**
     * @return array<int, array<string, mixed>>
     */
    private function buildFamilyTree(): array
    {
        return [
            // ── Indo-European (ID 1) ────────────────────────────
            [
                'family_id' => 1,
                'name' => 'Indo-European',
                'parent_family_id' => null,
                'depth_level' => 0,
                'proto_language' => 'Proto-Indo-European',
                'estimated_origin' => '-4500~',
                'estimated_homeland' => 'Pontic-Caspian steppe',
                'living_languages' => 445,
                'status' => 'major',
            ],
            // Indo-Iranian (ID 2)
            [
                'family_id' => 2,
                'name' => 'Indo-Iranian',
                'parent_family_id' => 1,
                'depth_level' => 1,
                'proto_language' => 'Proto-Indo-Iranian',
                'estimated_origin' => '-2500~',
                'estimated_homeland' => 'Central Asia',
                'living_languages' => 308,
                'status' => 'major',
            ],
            // Indo-Aryan (ID 3)
            [
                'family_id' => 3,
                'name' => 'Indo-Aryan',
                'parent_family_id' => 2,
                'depth_level' => 2,
                'proto_language' => 'Proto-Indo-Aryan',
                'estimated_origin' => '-2000~',
                'estimated_homeland' => 'South Asia',
                'living_languages' => 219,
                'status' => 'major',
            ],
            // Iranian (ID 4)
            [
                'family_id' => 4,
                'name' => 'Iranian',
                'parent_family_id' => 2,
                'depth_level' => 2,
                'proto_language' => 'Proto-Iranian',
                'estimated_origin' => '-1500~',
                'estimated_homeland' => 'Iranian Plateau',
                'living_languages' => 86,
                'status' => 'major',
            ],
            // Hellenic (ID 5)
            [
                'family_id' => 5,
                'name' => 'Hellenic',
                'parent_family_id' => 1,
                'depth_level' => 1,
                'proto_language' => 'Proto-Hellenic',
                'estimated_origin' => '-2000~',
                'estimated_homeland' => 'Greece / Southern Balkans',
                'living_languages' => 1,
                'status' => 'major',
            ],
            // Italic (ID 6)
            [
                'family_id' => 6,
                'name' => 'Italic',
                'parent_family_id' => 1,
                'depth_level' => 1,
                'proto_language' => 'Proto-Italic',
                'estimated_origin' => '-1500~',
                'estimated_homeland' => 'Italian Peninsula',
                'living_languages' => 44,
                'status' => 'major',
            ],
            // Romance (ID 7)
            [
                'family_id' => 7,
                'name' => 'Romance',
                'parent_family_id' => 6,
                'depth_level' => 2,
                'proto_language' => 'Vulgar Latin',
                'estimated_origin' => '300~',
                'estimated_homeland' => 'Roman Empire',
                'living_languages' => 43,
                'status' => 'major',
            ],
            // Celtic (ID 8)
            [
                'family_id' => 8,
                'name' => 'Celtic',
                'parent_family_id' => 1,
                'depth_level' => 1,
                'proto_language' => 'Proto-Celtic',
                'estimated_origin' => '-1300~',
                'estimated_homeland' => 'Central Europe',
                'living_languages' => 6,
                'status' => 'minor',
            ],
            // Germanic (ID 9)
            [
                'family_id' => 9,
                'name' => 'Germanic',
                'parent_family_id' => 1,
                'depth_level' => 1,
                'proto_language' => 'Proto-Germanic',
                'estimated_origin' => '-500~',
                'estimated_homeland' => 'Southern Scandinavia',
                'living_languages' => 47,
                'status' => 'major',
            ],
            // North Germanic (ID 10)
            [
                'family_id' => 10,
                'name' => 'North Germanic',
                'parent_family_id' => 9,
                'depth_level' => 2,
                'proto_language' => 'Proto-Norse',
                'estimated_origin' => '200~',
                'estimated_homeland' => 'Scandinavia',
                'living_languages' => 5,
                'status' => 'major',
            ],
            // West Germanic (ID 11)
            [
                'family_id' => 11,
                'name' => 'West Germanic',
                'parent_family_id' => 9,
                'depth_level' => 2,
                'proto_language' => 'Proto-West-Germanic',
                'estimated_origin' => '200~',
                'estimated_homeland' => 'Northern Germany / Netherlands',
                'living_languages' => 40,
                'status' => 'major',
            ],
            // Balto-Slavic (ID 12)
            [
                'family_id' => 12,
                'name' => 'Balto-Slavic',
                'parent_family_id' => 1,
                'depth_level' => 1,
                'proto_language' => 'Proto-Balto-Slavic',
                'estimated_origin' => '-1500~',
                'estimated_homeland' => 'Eastern Europe',
                'living_languages' => 20,
                'status' => 'major',
            ],
            // Baltic (ID 13)
            [
                'family_id' => 13,
                'name' => 'Baltic',
                'parent_family_id' => 12,
                'depth_level' => 2,
                'proto_language' => 'Proto-Baltic',
                'estimated_origin' => '-1000~',
                'estimated_homeland' => 'Eastern Baltic coast',
                'living_languages' => 2,
                'status' => 'minor',
            ],
            // Slavic (ID 14)
            [
                'family_id' => 14,
                'name' => 'Slavic',
                'parent_family_id' => 12,
                'depth_level' => 2,
                'proto_language' => 'Proto-Slavic',
                'estimated_origin' => '-500~',
                'estimated_homeland' => 'Eastern Europe / Pripyat Marshes',
                'living_languages' => 18,
                'status' => 'major',
            ],
            // Armenian (ID 15)
            [
                'family_id' => 15,
                'name' => 'Armenian',
                'parent_family_id' => 1,
                'depth_level' => 1,
                'proto_language' => 'Proto-Armenian',
                'estimated_origin' => '-600~',
                'estimated_homeland' => 'Armenian Highlands',
                'living_languages' => 2,
                'status' => 'minor',
            ],
            // Albanian (ID 16)
            [
                'family_id' => 16,
                'name' => 'Albanian',
                'parent_family_id' => 1,
                'depth_level' => 1,
                'proto_language' => 'Proto-Albanian',
                'estimated_origin' => '-500~',
                'estimated_homeland' => 'Western Balkans',
                'living_languages' => 2,
                'status' => 'minor',
            ],
            // Tocharian (ID 17)
            [
                'family_id' => 17,
                'name' => 'Tocharian',
                'parent_family_id' => 1,
                'depth_level' => 1,
                'proto_language' => 'Proto-Tocharian',
                'estimated_origin' => '-1000~',
                'estimated_homeland' => 'Tarim Basin, Central Asia',
                'living_languages' => 0,
                'status' => 'extinct',
            ],
            // Anatolian (ID 18)
            [
                'family_id' => 18,
                'name' => 'Anatolian',
                'parent_family_id' => 1,
                'depth_level' => 1,
                'proto_language' => 'Proto-Anatolian',
                'estimated_origin' => '-2500~',
                'estimated_homeland' => 'Anatolia',
                'living_languages' => 0,
                'status' => 'extinct',
            ],

            // ── Afro-Asiatic (ID 20) ───────────────────────────
            [
                'family_id' => 20,
                'name' => 'Afro-Asiatic',
                'parent_family_id' => null,
                'depth_level' => 0,
                'proto_language' => 'Proto-Afro-Asiatic',
                'estimated_origin' => '-12000~',
                'estimated_homeland' => 'Northeast Africa or Levant (debated)',
                'living_languages' => 375,
                'status' => 'major',
            ],
            // Semitic (ID 21)
            [
                'family_id' => 21,
                'name' => 'Semitic',
                'parent_family_id' => 20,
                'depth_level' => 1,
                'proto_language' => 'Proto-Semitic',
                'estimated_origin' => '-3750~',
                'estimated_homeland' => 'Levant or Ethiopian Highlands',
                'living_languages' => 77,
                'status' => 'major',
            ],
            // Egyptian (ID 22)
            [
                'family_id' => 22,
                'name' => 'Egyptian',
                'parent_family_id' => 20,
                'depth_level' => 1,
                'proto_language' => null,
                'estimated_origin' => '-3200~',
                'estimated_homeland' => 'Nile Valley',
                'living_languages' => 0,
                'status' => 'extinct',
            ],
            // Berber (ID 23)
            [
                'family_id' => 23,
                'name' => 'Berber',
                'parent_family_id' => 20,
                'depth_level' => 1,
                'proto_language' => 'Proto-Berber',
                'estimated_origin' => '-3000~',
                'estimated_homeland' => 'North Africa',
                'living_languages' => 26,
                'status' => 'major',
            ],
            // Cushitic (ID 24)
            [
                'family_id' => 24,
                'name' => 'Cushitic',
                'parent_family_id' => 20,
                'depth_level' => 1,
                'proto_language' => 'Proto-Cushitic',
                'estimated_origin' => '-5000~',
                'estimated_homeland' => 'Horn of Africa',
                'living_languages' => 47,
                'status' => 'major',
            ],
            // Chadic (ID 25)
            [
                'family_id' => 25,
                'name' => 'Chadic',
                'parent_family_id' => 20,
                'depth_level' => 1,
                'proto_language' => 'Proto-Chadic',
                'estimated_origin' => '-5000~',
                'estimated_homeland' => 'Lake Chad basin',
                'living_languages' => 195,
                'status' => 'major',
            ],

            // ── Sino-Tibetan (ID 30) ───────────────────────────
            [
                'family_id' => 30,
                'name' => 'Sino-Tibetan',
                'parent_family_id' => null,
                'depth_level' => 0,
                'proto_language' => 'Proto-Sino-Tibetan',
                'estimated_origin' => '-6000~',
                'estimated_homeland' => 'Northern China / Yellow River basin',
                'living_languages' => 450,
                'status' => 'major',
            ],
            // Sinitic (ID 31)
            [
                'family_id' => 31,
                'name' => 'Sinitic',
                'parent_family_id' => 30,
                'depth_level' => 1,
                'proto_language' => 'Proto-Sinitic',
                'estimated_origin' => '-3000~',
                'estimated_homeland' => 'Yellow River basin',
                'living_languages' => 14,
                'status' => 'major',
            ],
            // Tibeto-Burman (ID 32)
            [
                'family_id' => 32,
                'name' => 'Tibeto-Burman',
                'parent_family_id' => 30,
                'depth_level' => 1,
                'proto_language' => 'Proto-Tibeto-Burman',
                'estimated_origin' => '-4000~',
                'estimated_homeland' => 'Eastern Himalayas / Sichuan',
                'living_languages' => 435,
                'status' => 'major',
            ],

            // ── Stand-alone families (depth 0) ──────────────────
            // Uralic (ID 40)
            [
                'family_id' => 40,
                'name' => 'Uralic',
                'parent_family_id' => null,
                'depth_level' => 0,
                'proto_language' => 'Proto-Uralic',
                'estimated_origin' => '-4000~',
                'estimated_homeland' => 'Western Urals',
                'living_languages' => 38,
                'status' => 'major',
            ],
            // Altaic (ID 41) — controversial grouping
            [
                'family_id' => 41,
                'name' => 'Altaic',
                'parent_family_id' => null,
                'depth_level' => 0,
                'proto_language' => null,
                'estimated_origin' => null,
                'estimated_homeland' => 'Central / Northeast Asia',
                'living_languages' => 66,
                'status' => 'major',
            ],
            // Austronesian (ID 42)
            [
                'family_id' => 42,
                'name' => 'Austronesian',
                'parent_family_id' => null,
                'depth_level' => 0,
                'proto_language' => 'Proto-Austronesian',
                'estimated_origin' => '-3000~',
                'estimated_homeland' => 'Taiwan',
                'living_languages' => 1257,
                'status' => 'major',
            ],
            // Niger-Congo (ID 43)
            [
                'family_id' => 43,
                'name' => 'Niger-Congo',
                'parent_family_id' => null,
                'depth_level' => 0,
                'proto_language' => 'Proto-Niger-Congo',
                'estimated_origin' => '-5000~',
                'estimated_homeland' => 'West Africa',
                'living_languages' => 1542,
                'status' => 'major',
            ],
            // Dravidian (ID 44)
            [
                'family_id' => 44,
                'name' => 'Dravidian',
                'parent_family_id' => null,
                'depth_level' => 0,
                'proto_language' => 'Proto-Dravidian',
                'estimated_origin' => '-4000~',
                'estimated_homeland' => 'Indian subcontinent',
                'living_languages' => 80,
                'status' => 'major',
            ],
            // Kartvelian (ID 45)
            [
                'family_id' => 45,
                'name' => 'Kartvelian',
                'parent_family_id' => null,
                'depth_level' => 0,
                'proto_language' => 'Proto-Kartvelian',
                'estimated_origin' => '-3000~',
                'estimated_homeland' => 'South Caucasus',
                'living_languages' => 4,
                'status' => 'minor',
            ],

            // ── Isolates (depth 0, status = isolate) ────────────
            // Basque (ID 50)
            [
                'family_id' => 50,
                'name' => 'Basque',
                'parent_family_id' => null,
                'depth_level' => 0,
                'proto_language' => 'Proto-Basque',
                'estimated_origin' => null,
                'estimated_homeland' => 'Western Pyrenees',
                'living_languages' => 1,
                'status' => 'isolate',
            ],
            // Sumerian (ID 51)
            [
                'family_id' => 51,
                'name' => 'Sumerian',
                'parent_family_id' => null,
                'depth_level' => 0,
                'proto_language' => null,
                'estimated_origin' => '-3500~',
                'estimated_homeland' => 'Southern Mesopotamia',
                'living_languages' => 0,
                'status' => 'isolate',
            ],
            // Elamite (ID 52)
            [
                'family_id' => 52,
                'name' => 'Elamite',
                'parent_family_id' => null,
                'depth_level' => 0,
                'proto_language' => null,
                'estimated_origin' => '-2600~',
                'estimated_homeland' => 'Southwestern Iran',
                'living_languages' => 0,
                'status' => 'isolate',
            ],
            // Etruscan (ID 53)
            [
                'family_id' => 53,
                'name' => 'Etruscan',
                'parent_family_id' => null,
                'depth_level' => 0,
                'proto_language' => null,
                'estimated_origin' => '-700~',
                'estimated_homeland' => 'Central Italy',
                'living_languages' => 0,
                'status' => 'isolate',
            ],
        ];
    }
}
