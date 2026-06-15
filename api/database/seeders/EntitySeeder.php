<?php

declare(strict_types=1);

namespace Database\Seeders;

use Database\Seeders\Traits\PgArrayLiteral;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;

/**
 * Seeds the entities table with curated historical data across all 5 groups.
 *
 * Uses DB::table()->insert() with raw PG enum values (consistent with
 * reference table seeders). Geometry is added via separate UPDATE statements
 * using ST_GeomFromGeoJSON because PG geometry columns cannot accept JSON
 * strings through regular inserts.
 */
class EntitySeeder extends Seeder
{
    use PgArrayLiteral;

    /**
     * @var array<string, array{lat: float, lon: float}>
     */
    private array $geometries = [];

    /**
     * @var array<string, string>
     */
    private array $territories = [];

    public function run(): void
    {
        $entities = $this->buildEntities();

        foreach ($entities as $entity) {
            $id = $entity['entity_id'];
            $legacyAlternativeNames = $entity['alternative_names'] ?? null;
            $legacyTags = $entity['tags'] ?? null;
            $legacyTemporalStart = $entity['temporal_start'] ?? null;
            $legacyTemporalEnd = $entity['temporal_end'] ?? null;
            $legacyLocationName = $entity['location_name'] ?? null;

            unset(
                $entity['alternative_names'],
                $entity['tags'],
                $entity['temporal_start'],
                $entity['temporal_end'],
                $entity['temporal_start_year'],
                $entity['temporal_end_year'],
                $entity['location_name'],
            );

            DB::table('entities')->insert($entity);

            foreach ($this->parsePgTextArrayLiteral($legacyAlternativeNames) as $alias) {
                DB::table('entity_aliases')->insert([
                    'alias_id' => DB::raw('gen_random_uuid()'),
                    'entity_id' => $id,
                    'name' => $alias,
                    'is_primary' => false,
                    'created_at' => now(),
                    'updated_at' => now(),
                ]);
            }

            foreach ($this->parsePgTextArrayLiteral($legacyTags) as $tag) {
                DB::table('entity_tags')->insert([
                    'entity_tag_id' => DB::raw('gen_random_uuid()'),
                    'entity_id' => $id,
                    'tag' => $tag,
                    'created_at' => now(),
                    'updated_at' => now(),
                ]);
            }

            if ($legacyTemporalStart !== null || $legacyTemporalEnd !== null) {
                DB::table('entity_temporal_ranges')->insert([
                    'temporal_range_id' => DB::raw('gen_random_uuid()'),
                    'entity_id' => $id,
                    'range_type' => 'primary',
                    'start_year' => $legacyTemporalStart !== null ? $this->extractYear((string) $legacyTemporalStart) : null,
                    'end_year' => $legacyTemporalEnd !== null ? $this->extractYear((string) $legacyTemporalEnd) : null,
                    'start_date' => $legacyTemporalStart,
                    'end_date' => $legacyTemporalEnd,
                    'duration_type' => $entity['duration_type'] ?? null,
                    'date_method' => $entity['date_method'] ?? null,
                    'date_confidence' => $entity['date_confidence'] ?? null,
                    'is_primary' => true,
                    'created_at' => now(),
                    'updated_at' => now(),
                ]);
            }

            if ($legacyLocationName !== null || isset($this->geometries[$id]) || isset($this->territories[$id])) {
                $geomExpression = 'NULL';
                if (isset($this->geometries[$id])) {
                    $coords = $this->geometries[$id];
                    $geomExpression = sprintf('ST_SetSRID(ST_MakePoint(%F, %F), 4326)', $coords['lon'], $coords['lat']);
                }

                $territoryExpression = 'NULL';
                if (isset($this->territories[$id])) {
                    $territoryExpression = "ST_SetSRID(ST_GeomFromGeoJSON('".str_replace("'", "''", $this->territories[$id])."'), 4326)";
                }

                DB::statement(
                    "INSERT INTO entity_locations (
                        location_id, entity_id, location_name, geom, territory_geom,
                        location_method, location_confidence, is_primary, created_at, updated_at
                    ) VALUES (
                        gen_random_uuid(), ?, ?, {$geomExpression}, {$territoryExpression},
                        ?::location_resolution_method, ?::confidence_level, true, NOW(), NOW()
                    )",
                    [
                        $id,
                        $legacyLocationName,
                        $entity['location_method'] ?? null,
                        $entity['location_confidence'] ?? null,
                    ],
                );
            }
        }
    }

    /** @return list<string> */
    private function parsePgTextArrayLiteral(mixed $value): array
    {
        if (! is_string($value) || $value === '' || $value === '{}') {
            return [];
        }

        $trimmed = trim($value, '{}');
        if ($trimmed === '') {
            return [];
        }

        /** @var list<string> $items */
        $items = str_getcsv($trimmed);

        return array_values(array_filter(array_map('trim', $items), static fn (string $item): bool => $item !== ''));
    }

    private function extractYear(string $value): ?int
    {
        if (preg_match('/^-?\d+/', trim($value), $matches) !== 1) {
            return null;
        }

        return (int) $matches[0];
    }

    /**
     * Build the complete list of entity records.
     *
     * @return list<array<string, mixed>>
     */
    private function buildEntities(): array
    {
        $now = now();

        return [
            // ── POLITY ──────────────────────────────────────
            ...$this->polityEntities($now),

            // ── PLACE ───────────────────────────────────────
            ...$this->placeEntities($now),

            // ── EVENT ───────────────────────────────────────
            ...$this->eventEntities($now),

            // ── ECONOMY ─────────────────────────────────────
            ...$this->economyEntities($now),

            // ── CULTURE ─────────────────────────────────────
            ...$this->cultureEntities($now),
        ];
    }

    /**
     * @return list<array<string, mixed>>
     */
    private function polityEntities(mixed $now): array
    {
        // Roman Empire
        $romanId = '10000000-0000-0000-0000-000000000001';
        $this->geometries[$romanId] = ['lat' => 41.9028, 'lon' => 12.4964];
        $this->territories[$romanId] = json_encode([
            'type' => 'Polygon',
            'coordinates' => [[[-9.5, 36.0], [35.0, 36.0], [35.0, 55.0], [-9.5, 55.0], [-9.5, 36.0]]],
        ]);

        // Ottoman Empire
        $ottomanId = '10000000-0000-0000-0000-000000000002';
        $this->geometries[$ottomanId] = ['lat' => 41.0082, 'lon' => 28.9784];
        $this->territories[$ottomanId] = json_encode([
            'type' => 'Polygon',
            'coordinates' => [[[25.0, 32.0], [45.0, 32.0], [45.0, 42.0], [25.0, 42.0], [25.0, 32.0]]],
        ]);

        // Ptolemaic Dynasty
        $ptolemyId = '10000000-0000-0000-0000-000000000003';
        $this->geometries[$ptolemyId] = ['lat' => 31.2001, 'lon' => 29.9187];
        $this->territories[$ptolemyId] = json_encode([
            'type' => 'Polygon',
            'coordinates' => [[[24.7, 22.0], [37.0, 22.0], [37.0, 32.0], [24.7, 32.0], [24.7, 22.0]]],
        ]);

        // Julius Caesar
        $caesarId = '10000000-0000-0000-0000-000000000004';
        $this->geometries[$caesarId] = ['lat' => 41.9028, 'lon' => 12.4964];

        // Genghis Khan
        $genghisId = '10000000-0000-0000-0000-000000000005';
        $this->geometries[$genghisId] = ['lat' => 47.9185, 'lon' => 106.9177];

        // Praetorian Guard
        $praetorianId = '10000000-0000-0000-0000-000000000006';
        $this->geometries[$praetorianId] = ['lat' => 41.9028, 'lon' => 12.4964];

        // Mongol Empire
        $mongolId = '10000000-0000-0000-0000-000000000007';
        $this->geometries[$mongolId] = ['lat' => 47.9185, 'lon' => 106.9177];
        $this->territories[$mongolId] = json_encode([
            'type' => 'Polygon',
            'coordinates' => [[[40.0, 30.0], [135.0, 30.0], [135.0, 60.0], [40.0, 60.0], [40.0, 30.0]]],
        ]);

        // Byzantine Empire
        $byzantineId = '10000000-0000-0000-0000-000000000008';
        $this->geometries[$byzantineId] = ['lat' => 41.0082, 'lon' => 28.9784];
        $this->territories[$byzantineId] = json_encode([
            'type' => 'Polygon',
            'coordinates' => [[[26.0, 36.0], [40.0, 36.0], [40.0, 43.0], [26.0, 43.0], [26.0, 36.0]]],
        ]);

        // Mehmed II
        $mehmedId = '10000000-0000-0000-0000-000000000009';
        $this->geometries[$mehmedId] = ['lat' => 41.0082, 'lon' => 28.9784];

        // Constantine XI Palaiologos
        $constantineXiId = '10000000-0000-0000-0000-000000000010';
        $this->geometries[$constantineXiId] = ['lat' => 41.0082, 'lon' => 28.9784];

        // Murad II
        $muradId = '10000000-0000-0000-0000-000000000011';
        $this->geometries[$muradId] = ['lat' => 41.6742, 'lon' => 26.5623];

        return [
            [
                'entity_id' => $romanId,
                'name' => 'Roman Empire',
                'entity_type' => 'political_entity',
                'entity_group' => 'POLITY',
                'summary' => 'The Roman Empire was the post-Republican phase of ancient Roman civilization, characterized by autocratic government headed by an emperor and large territorial holdings around the Mediterranean Sea in Europe, North Africa, and Western Asia.',
                'significance' => 'One of the largest empires in ancient history, profoundly shaping Western civilization through law, governance, engineering, language, and culture.',
                'impact_score' => 98,
                'temporal_start' => '-0027',
                'temporal_end' => '0476',
                'location_name' => 'Rome, Italia',
                'wikidata_id' => 'Q2277',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 10,
                'icon_class' => 'crown',
                'tags' => $this->textArray(['empire', 'rome', 'ancient', 'mediterranean', 'latin']),
                'alternative_names' => $this->textArray(['Imperium Romanum', 'SPQR']),
                'attributes' => json_encode([
                    'political_subtype' => 'empire',
                    'government_type' => 'bureaucratic_centralized',
                    'succession_type' => 'military_acclamation',
                    'date_raw' => '27 BCE – 476 CE',
                    'entity_color' => '#8B0000',
                ]),
                'source_citations' => json_encode([['source' => 'Gibbon, Decline and Fall', 'year' => 1776]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $ottomanId,
                'name' => 'Ottoman Empire',
                'entity_type' => 'political_entity',
                'entity_group' => 'POLITY',
                'summary' => 'The Ottoman Empire was a transcontinental empire founded in 1299 by Oghuz Turkic tribes under Osman I in northwestern Anatolia. It became one of the most powerful states in the world during the 15th–17th centuries.',
                'significance' => 'Controlled southeast Europe, western Asia, and North Africa for over 600 years, serving as a bridge between Eastern and Western civilizations.',
                'impact_score' => 92,
                'temporal_start' => '1299',
                'temporal_end' => '1922',
                'location_name' => 'Constantinople (Istanbul)',
                'wikidata_id' => 'Q12560',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 9,
                'icon_class' => 'crown',
                'tags' => $this->textArray(['empire', 'ottoman', 'islamic', 'anatolia', 'balkans']),
                'alternative_names' => $this->textArray(['Devlet-i ʿAliyye-i ʿOsmâniyye', 'Sublime Ottoman State']),
                'attributes' => json_encode([
                    'political_subtype' => 'sultanate',
                    'government_type' => 'absolute_monarchy',
                    'succession_type' => 'agnatic',
                    'date_raw' => '1299 – 1922 CE',
                    'entity_color' => '#006400',
                ]),
                'source_citations' => json_encode([['source' => 'Finkel, Osman\'s Dream', 'year' => 2005]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $ptolemyId,
                'name' => 'Ptolemaic Dynasty',
                'entity_type' => 'dynasty',
                'entity_group' => 'POLITY',
                'summary' => 'The Ptolemaic dynasty was a Macedonian Greek royal family which ruled the Ptolemaic Kingdom in Egypt during the Hellenistic period, from 305 BCE to 30 BCE.',
                'significance' => 'Last dynasty of ancient Egypt; patronized the Great Library of Alexandria and integrated Greek and Egyptian cultures.',
                'impact_score' => 78,
                'temporal_start' => '-0305',
                'temporal_end' => '-0030',
                'location_name' => 'Alexandria, Egypt',
                'wikidata_id' => 'Q37920',
                'verification_status' => 'human_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 7,
                'icon_class' => 'dynasty_tree',
                'tags' => $this->textArray(['dynasty', 'hellenistic', 'egypt', 'ptolemy', 'macedonian']),
                'alternative_names' => $this->textArray(['Ptolemies', 'Lagid dynasty']),
                'attributes' => json_encode([
                    'government_type' => 'absolute_monarchy',
                    'succession_type' => 'primogeniture',
                    'founding_event' => 'Ptolemy I proclaimed king following the Wars of the Diadochi',
                    'ethnic_origin' => 'Macedonian Greek',
                    'legitimacy_basis' => 'Conquest and divine kingship fused with Egyptian pharaonic tradition',
                    'date_raw' => '305 BCE – 30 BCE',
                    'entity_color' => '#DAA520',
                ]),
                'source_citations' => json_encode([['source' => 'Hölbl, A History of the Ptolemaic Empire', 'year' => 2001]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $caesarId,
                'name' => 'Gaius Julius Caesar',
                'entity_type' => 'person',
                'entity_group' => 'POLITY',
                'summary' => 'Roman statesman, general, and dictator who played a critical role in the events that led to the demise of the Roman Republic and the rise of the Roman Empire.',
                'significance' => 'His crossing of the Rubicon and subsequent civil war fundamentally transformed Roman governance. His assassination triggered the final round of civil wars that ended the Republic.',
                'impact_score' => 95,
                'temporal_start' => '-0100',
                'temporal_end' => '-0044',
                'location_name' => 'Rome, Roman Republic',
                'wikidata_id' => 'Q1048',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'source_database',
                'display_priority' => 10,
                'icon_class' => 'person',
                'tags' => $this->textArray(['roman', 'dictator', 'general', 'politician', 'assassination']),
                'alternative_names' => $this->textArray(['Caesar', 'Divus Iulius']),
                'attributes' => json_encode([
                    'gender' => 'male',
                    'birth_date' => '100 BCE',
                    'death_date' => '44 BCE',
                    'ethnicity' => 'Roman (patrician)',
                    'cause_of_death' => 'Assassinated on the Ides of March by a senatorial conspiracy led by Brutus and Cassius',
                    'date_raw' => '100 BCE – 44 BCE (Ides of March)',
                    'entity_color' => '#800020',
                ]),
                'source_citations' => json_encode([['source' => 'Suetonius, The Twelve Caesars', 'year' => 121]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $genghisId,
                'name' => 'Genghis Khan',
                'entity_type' => 'person',
                'entity_group' => 'POLITY',
                'summary' => 'Founder and first Great Khan of the Mongol Empire, which became the largest contiguous land empire in history after his death.',
                'significance' => 'United the Mongol tribes, established the Yassa legal code, and created an empire stretching from China to Eastern Europe, reshaping trade, culture, and demographics across Eurasia.',
                'impact_score' => 96,
                'temporal_start' => '1162',
                'temporal_end' => '1227',
                'location_name' => 'Khentii Mountains, Mongolia',
                'wikidata_id' => 'Q720',
                'verification_status' => 'expert_verified',
                'confidence' => 'medium',
                'date_method' => 'nlp_approximate',
                'date_confidence' => 'medium',
                'duration_type' => 'period',
                'location_confidence' => 'medium',
                'location_method' => 'wikidata',
                'display_priority' => 10,
                'icon_class' => 'person',
                'tags' => $this->textArray(['mongol', 'khan', 'conqueror', 'steppe', 'empire']),
                'alternative_names' => $this->textArray(['Temüjin', 'Chinggis Khaan']),
                'attributes' => json_encode([
                    'gender' => 'male',
                    'birth_date' => 'c. 1162 CE',
                    'death_date' => '1227 CE',
                    'ethnicity' => 'Mongol (Borjigin clan)',
                    'cause_of_death' => 'Uncertain; possibly injuries from a fall from his horse during the Xi Xia campaign',
                    'date_raw' => 'c. 1162 – 1227 CE',
                    'entity_color' => '#4B3621',
                ]),
                'source_citations' => json_encode([['source' => 'The Secret History of the Mongols', 'year' => 1240]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $praetorianId,
                'name' => 'Praetorian Guard',
                'entity_type' => 'military_unit',
                'entity_group' => 'POLITY',
                'summary' => 'An elite unit of the Roman army that served as the personal bodyguard of the Roman emperors from Augustus until their disbandment by Constantine I.',
                'significance' => 'Wielded enormous political influence, playing kingmaker in multiple imperial successions and assassinating several emperors.',
                'impact_score' => 72,
                'temporal_start' => '-0027',
                'temporal_end' => '0312',
                'location_name' => 'Castra Praetoria, Rome',
                'wikidata_id' => 'Q131756',
                'verification_status' => 'human_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'source_database',
                'display_priority' => 6,
                'icon_class' => 'shield',
                'tags' => $this->textArray(['roman', 'military', 'guard', 'praetorian', 'elite']),
                'alternative_names' => $this->textArray(['Cohortes Praetoriae']),
                'attributes' => json_encode([
                    'unit_subtype' => 'guard',
                    'composition' => 'professional',
                    'date_raw' => '27 BCE – 312 CE',
                    'entity_color' => '#B22222',
                ]),
                'source_citations' => json_encode([['source' => 'Bingham, The Praetorian Guard', 'year' => 2013]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $mongolId,
                'name' => 'Mongol Empire',
                'entity_type' => 'political_entity',
                'entity_group' => 'POLITY',
                'summary' => 'The largest contiguous land empire in history, founded by Genghis Khan in 1206 and expanding across Eurasia through a combination of military conquest and diplomatic alliance.',
                'significance' => 'Connected East and West through the Pax Mongolica, enabling unprecedented trade and cultural exchange along the Silk Road while also causing massive destruction and demographic collapse.',
                'impact_score' => 97,
                'temporal_start' => '1206',
                'temporal_end' => '1368',
                'location_name' => 'Karakorum, Mongolia',
                'wikidata_id' => 'Q12557',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'period',
                'location_confidence' => 'medium',
                'location_method' => 'wikidata',
                'display_priority' => 10,
                'icon_class' => 'crown',
                'tags' => $this->textArray(['mongol', 'empire', 'steppe', 'conquest', 'eurasia']),
                'alternative_names' => $this->textArray(['Yeke Mongghol Ulus', 'Great Mongol Nation']),
                'attributes' => json_encode([
                    'political_subtype' => 'khanate',
                    'government_type' => 'tribal_chieftainship',
                    'succession_type' => 'elective',
                    'date_raw' => '1206 – 1368 CE',
                    'entity_color' => '#8B6914',
                ]),
                'source_citations' => json_encode([['source' => 'Morgan, The Mongols', 'year' => 1986]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $byzantineId,
                'name' => 'Byzantine Empire',
                'entity_type' => 'political_entity',
                'entity_group' => 'POLITY',
                'summary' => 'The continuation of the Roman Empire in its eastern provinces during Late Antiquity and the Middle Ages, centered on Constantinople and surviving for over a millennium after the fall of the Western Roman Empire.',
                'significance' => 'Preserved Greco-Roman knowledge and Orthodox Christianity, transmitted classical learning to the Islamic world and Renaissance Europe, and maintained a sophisticated administrative and legal tradition.',
                'impact_score' => 91,
                'temporal_start' => '0330',
                'temporal_end' => '1453',
                'location_name' => 'Constantinople (Istanbul)',
                'wikidata_id' => 'Q12544',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 9,
                'icon_class' => 'crown',
                'tags' => $this->textArray(['byzantine', 'roman', 'orthodox', 'medieval', 'constantinople']),
                'alternative_names' => $this->textArray(['Eastern Roman Empire', 'Romania', 'Basileia Rhomaion']),
                'attributes' => json_encode([
                    'political_subtype' => 'empire',
                    'government_type' => 'bureaucratic_centralized',
                    'succession_type' => 'military_acclamation',
                    'date_raw' => '330 CE – 1453 CE',
                    'entity_color' => '#4B0082',
                ]),
                'source_citations' => json_encode([['source' => 'Ostrogorsky, History of the Byzantine State', 'year' => 1969]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $mehmedId,
                'name' => 'Mehmed II',
                'entity_type' => 'person',
                'entity_group' => 'POLITY',
                'summary' => 'Ottoman sultan known as Mehmed the Conqueror, who captured Constantinople in 1453 and transformed the Ottoman state into an imperial power. He reigned 1444-1446 and 1451-1481.',
                'significance' => 'His conquest of Constantinople ended the Byzantine Empire and marked a major geopolitical shift between medieval and early modern Eurasia.',
                'impact_score' => 93,
                'temporal_start' => '1432',
                'temporal_end' => '1481',
                'location_name' => 'Edirne and Constantinople',
                'wikidata_id' => 'Q125052',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 10,
                'icon_class' => 'crown',
                'tags' => $this->textArray(['ottoman', 'sultan', 'constantinople', 'conqueror', '15th_century']),
                'alternative_names' => $this->textArray(['Mehmed the Conqueror', 'Fatih Sultan Mehmed']),
                'attributes' => json_encode([
                    'person_subtype' => 'ruler',
                    'date_raw' => '1432-1481 CE',
                    'entity_color' => '#8B0000',
                ]),
                'source_citations' => json_encode([['source' => 'İnalcık, The Ottoman Empire: The Classical Age', 'year' => 1973]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $constantineXiId,
                'name' => 'Constantine XI Palaiologos',
                'entity_type' => 'person',
                'entity_group' => 'POLITY',
                'summary' => 'Final Byzantine emperor (r. 1449-1453), killed during the defense of Constantinople in 1453.',
                'significance' => 'His death symbolized the end of the Byzantine imperial line and the fall of Eastern Roman sovereignty.',
                'impact_score' => 84,
                'temporal_start' => '1405',
                'temporal_end' => '1453',
                'location_name' => 'Constantinople',
                'wikidata_id' => 'Q161871',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 8,
                'icon_class' => 'crown',
                'tags' => $this->textArray(['byzantine', 'emperor', 'constantinople', '1453']),
                'alternative_names' => $this->textArray(['Constantine XI', 'Konstantinos XI Palaiologos']),
                'attributes' => json_encode([
                    'person_subtype' => 'ruler',
                    'date_raw' => '1405-1453 CE',
                    'entity_color' => '#4B0082',
                ]),
                'source_citations' => json_encode([['source' => 'Nicol, The Immortal Emperor', 'year' => 1992]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $muradId,
                'name' => 'Murad II',
                'entity_type' => 'person',
                'entity_group' => 'POLITY',
                'summary' => 'Ottoman sultan (r. 1421-1451, with a brief abdication), who stabilized Ottoman power in the Balkans and defeated crusader forces at Varna in 1444.',
                'significance' => 'His military and political consolidation enabled the later conquest of Constantinople under Mehmed II.',
                'impact_score' => 86,
                'temporal_start' => '1404',
                'temporal_end' => '1451',
                'location_name' => 'Edirne',
                'wikidata_id' => 'Q233171',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 8,
                'icon_class' => 'crown',
                'tags' => $this->textArray(['ottoman', 'sultan', 'varna', 'balkans']),
                'alternative_names' => $this->textArray(['Sultan Murad II']),
                'attributes' => json_encode([
                    'person_subtype' => 'ruler',
                    'date_raw' => '1404-1451 CE',
                    'entity_color' => '#B22222',
                ]),
                'source_citations' => json_encode([['source' => 'Imber, The Ottoman Empire 1300-1650', 'year' => 2002]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
        ];
    }

    /**
     * @return list<array<string, mixed>>
     */
    private function placeEntities(mixed $now): array
    {
        // Constantinople
        $constantinopleId = '20000000-0000-0000-0000-000000000001';
        $this->geometries[$constantinopleId] = ['lat' => 41.0082, 'lon' => 28.9784];

        // Great Wall
        $wallId = '20000000-0000-0000-0000-000000000002';
        $this->geometries[$wallId] = ['lat' => 40.4319, 'lon' => 116.5704];

        // Laurion Mines
        $laurionId = '20000000-0000-0000-0000-000000000003';
        $this->geometries[$laurionId] = ['lat' => 37.7278, 'lon' => 24.0549];

        // University of Bologna
        $bolognaId = '20000000-0000-0000-0000-000000000004';
        $this->geometries[$bolognaId] = ['lat' => 44.4949, 'lon' => 11.3464];

        // Angkor Wat
        $angkorId = '20000000-0000-0000-0000-000000000005';
        $this->geometries[$angkorId] = ['lat' => 13.4125, 'lon' => 103.8670];

        // Alexandria
        $alexandriaId = '20000000-0000-0000-0000-000000000006';
        $this->geometries[$alexandriaId] = ['lat' => 31.2001, 'lon' => 29.9187];

        // Edirne (Adrianople)
        $edirneId = '20000000-0000-0000-0000-000000000007';
        $this->geometries[$edirneId] = ['lat' => 41.6742, 'lon' => 26.5623];

        return [
            [
                'entity_id' => $constantinopleId,
                'name' => 'Constantinople',
                'entity_type' => 'city',
                'entity_group' => 'PLACE',
                'summary' => 'Capital of the Eastern Roman (Byzantine) Empire, founded by Emperor Constantine I in 330 CE on the site of the ancient Greek colony of Byzantium.',
                'significance' => 'Strategic crossroads between Europe and Asia, center of Orthodox Christianity, and the wealthiest city in Europe for nearly a millennium.',
                'impact_score' => 94,
                'temporal_start' => '0330',
                'temporal_end' => '1453',
                'location_name' => 'Istanbul, Turkey',
                'wikidata_id' => 'Q16869',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 9,
                'icon_class' => 'city',
                'tags' => $this->textArray(['byzantine', 'city', 'capital', 'trade', 'orthodox']),
                'alternative_names' => $this->textArray(['Byzantium', 'Istanbul', 'Nova Roma', 'Tsargrad']),
                'attributes' => json_encode([
                    'settlement_subtype' => 'capital_city',
                    'elevation_m' => 45,
                    'founding_legend' => 'Constantine I chose the site after divine vision, refounding the Greek colony of Byzantium as Nova Roma in 330 CE',
                    'date_raw' => '330 CE – 1453 CE (fall to Ottomans)',
                    'entity_color' => '#4B0082',
                ]),
                'source_citations' => json_encode([['source' => 'Norwich, Byzantium: The Early Centuries', 'year' => 1988]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $wallId,
                'name' => 'Great Wall of China',
                'entity_type' => 'infrastructure_monument',
                'entity_group' => 'PLACE',
                'summary' => 'A series of fortifications made of stone, brick, tamped earth, and other materials, built along the northern borders of China to protect against various nomadic groups of the Eurasian Steppe.',
                'significance' => 'The most extensive construction project in human history, representing centuries of Chinese defensive strategy and labor mobilization.',
                'impact_score' => 90,
                'temporal_start' => '-0700',
                'temporal_end' => '1644',
                'location_name' => 'Northern China',
                'wikidata_id' => 'Q12501',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'nlp_approximate',
                'date_confidence' => 'medium',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 9,
                'icon_class' => 'monument',
                'tags' => $this->textArray(['china', 'wall', 'fortification', 'defense', 'monument']),
                'alternative_names' => $this->textArray(['Wànlǐ Chángchéng', 'Long Wall']),
                'attributes' => json_encode([
                    'monument_subtype' => 'wall',
                    'construction_start' => '7th century BCE',
                    'construction_end' => '1644 CE',
                    'current_condition' => 'ruins',
                    'unesco_status' => 'UNESCO World Heritage Site (1987)',
                    'date_raw' => '7th century BCE – 1644 CE',
                    'entity_color' => '#808080',
                ]),
                'source_citations' => json_encode([['source' => 'Waldron, The Great Wall of China', 'year' => 1990]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $laurionId,
                'name' => 'Silver Mines of Laurion',
                'entity_type' => 'extraction_infra',
                'entity_group' => 'PLACE',
                'summary' => 'Ancient silver mining complex in Attica that provided much of the wealth funding Athenian naval power and democracy.',
                'significance' => 'The silver from Laurion financed the Athenian fleet that defeated Persia at Salamis and underwrote the golden age of Athens.',
                'impact_score' => 68,
                'temporal_start' => '-0600',
                'temporal_end' => '-0100',
                'location_name' => 'Laurion, Attica, Greece',
                'wikidata_id' => 'Q1515834',
                'verification_status' => 'human_verified',
                'confidence' => 'medium',
                'date_method' => 'nlp_approximate',
                'date_confidence' => 'medium',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'pleiades',
                'display_priority' => 5,
                'icon_class' => 'pickaxe',
                'tags' => $this->textArray(['mining', 'silver', 'athens', 'economy', 'ancient_greece']),
                'alternative_names' => $this->textArray(['Lavrion', 'Laurium']),
                'attributes' => json_encode([
                    'infra_subtype' => 'mine',
                    'scale' => 'large',
                    'date_raw' => '6th century BCE – 1st century BCE',
                    'entity_color' => '#C0C0C0',
                ]),
                'source_citations' => json_encode([['source' => 'Conophagos, Le Laurium antique', 'year' => 1980]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $bolognaId,
                'name' => 'University of Bologna',
                'entity_type' => 'educational_institution',
                'entity_group' => 'PLACE',
                'summary' => 'The oldest university in continuous operation, founded in 1088 in Bologna, Italy. It became a model for European higher education.',
                'significance' => 'Pioneered the modern concept of the university, establishing student-organized governance and systematic legal scholarship that shaped Western education.',
                'impact_score' => 76,
                'temporal_start' => '1088',
                'temporal_end' => null,
                'location_name' => 'Bologna, Italy',
                'wikidata_id' => 'Q131262',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'ongoing',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 7,
                'icon_class' => 'university',
                'tags' => $this->textArray(['university', 'education', 'medieval', 'law', 'italy']),
                'alternative_names' => $this->textArray(['Alma Mater Studiorum', 'Universitas Bononiensis']),
                'attributes' => json_encode([
                    'institution_type' => 'university',
                    'library_holdings' => 'Extensive collection of Roman law texts; archive holds over 1 million volumes',
                    'date_raw' => '1088 CE – present',
                    'entity_color' => '#8B4513',
                ]),
                'source_citations' => json_encode([['source' => 'Rashdall, The Universities of Europe in the Middle Ages', 'year' => 1895]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $angkorId,
                'name' => 'Angkor Wat',
                'entity_type' => 'infrastructure_monument',
                'entity_group' => 'PLACE',
                'summary' => 'A Hindu-Buddhist temple complex in Cambodia, originally constructed as a Hindu temple dedicated to Vishnu for the Khmer Empire. It is the largest religious structure in the world.',
                'significance' => 'Represents the pinnacle of Khmer architecture and serves as a symbol of Cambodia, appearing on its national flag.',
                'impact_score' => 85,
                'temporal_start' => '1113',
                'temporal_end' => '1150',
                'location_name' => 'Angkor, Cambodia',
                'wikidata_id' => 'Q43473',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'medium',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 8,
                'icon_class' => 'temple',
                'tags' => $this->textArray(['khmer', 'temple', 'cambodia', 'hindu', 'buddhist']),
                'alternative_names' => $this->textArray(['Nokor Wat', 'City Temple']),
                'attributes' => json_encode([
                    'monument_subtype' => 'temple',
                    'construction_start' => '1113 CE',
                    'construction_end' => '1150 CE',
                    'current_condition' => 'extant',
                    'unesco_status' => 'UNESCO World Heritage Site (1992, part of Angkor)',
                    'date_raw' => 'c. 1113 – 1150 CE (construction period)',
                    'entity_color' => '#DAA520',
                ]),
                'source_citations' => json_encode([['source' => 'Higham, The Civilization of Angkor', 'year' => 2001]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $alexandriaId,
                'name' => 'Alexandria',
                'entity_type' => 'city',
                'entity_group' => 'PLACE',
                'summary' => 'A Hellenistic city founded by Alexander the Great in 331 BCE on the Egyptian Mediterranean coast, which became the intellectual capital of the ancient world under Ptolemaic rule.',
                'significance' => 'Home to the Great Library and Mouseion, it was the foremost center of learning in antiquity, attracting scholars from across the Mediterranean and producing advances in mathematics, astronomy, and medicine.',
                'impact_score' => 92,
                'temporal_start' => '-0331',
                'temporal_end' => null,
                'location_name' => 'Alexandria, Egypt',
                'wikidata_id' => 'Q87',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'ongoing',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 9,
                'icon_class' => 'city',
                'tags' => $this->textArray(['hellenistic', 'egypt', 'library', 'learning', 'alexander']),
                'alternative_names' => $this->textArray(['Alexandreia', 'Al-Iskandariyya']),
                'attributes' => json_encode([
                    'settlement_subtype' => 'major_city',
                    'elevation_m' => 5,
                    'founding_legend' => 'Founded by Alexander the Great in 331 BCE; site chosen for its natural harbor between Lake Mareotis and the Mediterranean',
                    'date_raw' => '331 BCE – present (as modern Alexandria)',
                    'entity_color' => '#B8860B',
                ]),
                'source_citations' => json_encode([['source' => 'Fraser, Ptolemaic Alexandria', 'year' => 1972]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $edirneId,
                'name' => 'Edirne',
                'entity_type' => 'city',
                'entity_group' => 'PLACE',
                'summary' => 'Historic city in Thrace known as Adrianople, serving as a major Ottoman administrative and military center and imperial capital before 1453.',
                'significance' => 'Functioned as the Ottoman capital before the conquest of Constantinople and remained a key strategic gateway between Anatolia and the Balkans.',
                'impact_score' => 82,
                'temporal_start' => '0130',
                'temporal_end' => null,
                'location_name' => 'Edirne, Turkey',
                'wikidata_id' => 'Q1800',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'ongoing',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 8,
                'icon_class' => 'city',
                'tags' => $this->textArray(['ottoman', 'thrace', 'capital', 'adrianople']),
                'alternative_names' => $this->textArray(['Adrianople', 'Hadrianopolis']),
                'attributes' => json_encode([
                    'settlement_subtype' => 'major_city',
                    'date_raw' => 'Roman era to present; Ottoman capital 1369-1453',
                    'entity_color' => '#8B4513',
                ]),
                'source_citations' => json_encode([['source' => 'Finkel, Osman’s Dream', 'year' => 2005]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
        ];
    }

    /**
     * @return list<array<string, mixed>>
     */
    private function eventEntities(mixed $now): array
    {
        // Fall of Constantinople
        $fallId = '30000000-0000-0000-0000-000000000001';
        $this->geometries[$fallId] = ['lat' => 41.0082, 'lon' => 28.9784];

        // Hundred Years' War
        $hundredId = '30000000-0000-0000-0000-000000000002';
        $this->geometries[$hundredId] = ['lat' => 48.8566, 'lon' => 2.3522];

        // Battle of Thermopylae
        $thermoId = '30000000-0000-0000-0000-000000000003';
        $this->geometries[$thermoId] = ['lat' => 38.7967, 'lon' => 22.5340];

        // Treaty of Westphalia
        $westphaliaId = '30000000-0000-0000-0000-000000000004';
        $this->geometries[$westphaliaId] = ['lat' => 52.0293, 'lon' => 7.6276];

        // Black Death
        $plagueId = '30000000-0000-0000-0000-000000000005';
        $this->geometries[$plagueId] = ['lat' => 45.4408, 'lon' => 12.3155];

        // Gutenberg Printing Press
        $gutenbergId = '30000000-0000-0000-0000-000000000006';
        $this->geometries[$gutenbergId] = ['lat' => 49.9929, 'lon' => 8.2473];

        // Magna Carta
        $magnaId = '30000000-0000-0000-0000-000000000007';
        $this->geometries[$magnaId] = ['lat' => 51.4314, 'lon' => -0.5633];

        // Great Migration Period
        $migrationId = '30000000-0000-0000-0000-000000000008';
        $this->geometries[$migrationId] = ['lat' => 50.0, 'lon' => 20.0];

        // Battle of Varna
        $varnaId = '30000000-0000-0000-0000-000000000009';
        $this->geometries[$varnaId] = ['lat' => 43.2141, 'lon' => 27.9147];

        return [
            [
                'entity_id' => $fallId,
                'name' => 'Fall of Constantinople',
                'entity_type' => 'event_battle',
                'entity_group' => 'EVENT',
                'summary' => 'The capture of the capital of the Byzantine Empire by the Ottoman Empire on 29 May 1453, marking the end of the Roman Empire after nearly 1,500 years.',
                'significance' => 'Conventionally marks the end of the Middle Ages and the beginning of the Early Modern period. Triggered the westward migration of Greek scholars, contributing to the Renaissance.',
                'impact_score' => 96,
                'temporal_start' => '1453-04-06',
                'temporal_end' => '1453-05-29',
                'location_name' => 'Constantinople',
                'wikidata_id' => 'Q131800',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 10,
                'icon_class' => 'crossed_swords',
                'tags' => $this->textArray(['byzantine', 'ottoman', 'siege', 'constantinople', '1453']),
                'alternative_names' => $this->textArray(['Siege of Constantinople', 'Conquest of Constantinople']),
                'attributes' => json_encode([
                    'battle_subtype' => 'siege',
                    'outcome' => 'decisive_victory',
                    'victor_side' => 'Ottoman',
                    'tactical_notes' => 'Mehmed II deployed large cannon including the Basilica to breach the Theodosian Walls; Genoese and Venetian defenders unable to hold the sea walls against the Ottoman fleet dragged overland into the Golden Horn',
                    'date_raw' => '6 April – 29 May 1453',
                    'entity_color' => '#DC143C',
                ]),
                'source_citations' => json_encode([['source' => 'Runciman, The Fall of Constantinople 1453', 'year' => 1965]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $hundredId,
                'name' => 'Hundred Years\' War',
                'entity_type' => 'event_war',
                'entity_group' => 'EVENT',
                'summary' => 'A series of armed conflicts between the kingdoms of England and France from 1337 to 1453, rooted in disputes over the French crown and English territorial claims in France.',
                'significance' => 'Transformed medieval warfare, fostered national identities in both England and France, and saw the emergence of standing armies and gunpowder weapons in Europe.',
                'impact_score' => 86,
                'temporal_start' => '1337',
                'temporal_end' => '1453',
                'location_name' => 'France, England',
                'wikidata_id' => 'Q108478',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'period',
                'location_confidence' => 'medium',
                'location_method' => 'source_database',
                'display_priority' => 8,
                'icon_class' => 'crossed_swords',
                'tags' => $this->textArray(['war', 'medieval', 'england', 'france', 'chivalry']),
                'alternative_names' => $this->textArray(['Guerre de Cent Ans']),
                'attributes' => json_encode([
                    'war_subtype' => 'succession_war',
                    'casus_belli' => 'Edward III of England claimed the French throne through his mother Isabella, daughter of Philip IV of France',
                    'territorial_changes' => 'England lost virtually all French territories except Calais; French monarchy consolidated control over the realm',
                    'date_raw' => '1337 – 1453 CE',
                    'entity_color' => '#4169E1',
                ]),
                'source_citations' => json_encode([['source' => 'Sumption, The Hundred Years War', 'year' => 1990]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $thermoId,
                'name' => 'Battle of Thermopylae',
                'entity_type' => 'event_battle',
                'entity_group' => 'EVENT',
                'summary' => 'A famous last stand by a Greek force led by King Leonidas I of Sparta against the Persian army of Xerxes I in 480 BCE at the narrow coastal pass of Thermopylae.',
                'significance' => 'Became a symbol of courage against overwhelming odds. The delay allowed the Greek fleet to prepare for the decisive Battle of Salamis.',
                'impact_score' => 84,
                'temporal_start' => '-0480-08',
                'temporal_end' => '-0480-08',
                'location_name' => 'Thermopylae, Phthiotis, Greece',
                'wikidata_id' => 'Q151952',
                'verification_status' => 'human_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'medium',
                'duration_type' => 'point',
                'location_confidence' => 'high',
                'location_method' => 'pleiades',
                'display_priority' => 8,
                'icon_class' => 'shield',
                'tags' => $this->textArray(['sparta', 'persia', 'battle', 'greco-persian_wars', 'leonidas']),
                'alternative_names' => $this->textArray(['Thermopylai', 'Hot Gates']),
                'attributes' => json_encode([
                    'battle_subtype' => 'last_stand',
                    'outcome' => 'tactical_defeat',
                    'victor_side' => 'Persian',
                    'tactical_notes' => 'Leonidas held the pass for three days using the narrow terrain to neutralize Persian numerical advantage; betrayed by Ephialtes who revealed a mountain path allowing Persian flanking',
                    'date_raw' => 'August 480 BCE (3 days)',
                    'entity_color' => '#8B0000',
                ]),
                'source_citations' => json_encode([['source' => 'Herodotus, Histories, Book VII', 'year' => -440]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $westphaliaId,
                'name' => 'Peace of Westphalia',
                'entity_type' => 'event_treaty',
                'entity_group' => 'EVENT',
                'summary' => 'A series of treaties signed in 1648 ending the Thirty Years\' War in the Holy Roman Empire and the Eighty Years\' War between Spain and the Dutch Republic.',
                'significance' => 'Established the principle of state sovereignty and the modern concept of the nation-state, fundamentally reshaping the international order.',
                'impact_score' => 91,
                'temporal_start' => '1648-05-15',
                'temporal_end' => '1648-10-24',
                'location_name' => 'Münster and Osnabrück, Westphalia',
                'wikidata_id' => 'Q150793',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'point',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 9,
                'icon_class' => 'treaty_seal',
                'tags' => $this->textArray(['treaty', 'sovereignty', 'westphalia', 'thirty_years_war', 'international_law']),
                'alternative_names' => $this->textArray(['Westfälischer Friede', 'Pax Westphalica']),
                'attributes' => json_encode([
                    'treaty_subtype' => 'peace_treaty',
                    'key_provisions' => 'Recognized sovereignty of German princes over their territories; confirmed Dutch and Swiss independence; established religious toleration for Catholics, Lutherans, and Calvinists within the Empire',
                    'duration' => 'Permanent',
                    'date_raw' => '15 May – 24 October 1648',
                    'entity_color' => '#556B2F',
                ]),
                'source_citations' => json_encode([['source' => 'Croxton, Westphalia: The Last Christian Peace', 'year' => 2013]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $plagueId,
                'name' => 'Black Death',
                'entity_type' => 'epidemic_disease',
                'entity_group' => 'EVENT',
                'summary' => 'A devastating pandemic of bubonic plague that swept across Afro-Eurasia from 1346 to 1353, killing an estimated 75–200 million people.',
                'significance' => 'Killed 30–60% of Europe\'s population, triggering profound social, economic, and cultural upheaval including labor shortages, peasant revolts, and challenges to feudal authority.',
                'impact_score' => 97,
                'temporal_start' => '1346',
                'temporal_end' => '1353',
                'location_name' => 'Eurasia, North Africa',
                'wikidata_id' => 'Q42005',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'medium',
                'duration_type' => 'period',
                'location_confidence' => 'medium',
                'location_method' => 'source_database',
                'display_priority' => 10,
                'icon_class' => 'plague',
                'tags' => $this->textArray(['plague', 'pandemic', 'medieval', 'death', 'yersinia_pestis']),
                'alternative_names' => $this->textArray(['Great Pestilence', 'Great Mortality', 'Pestilencia']),
                'attributes' => json_encode([
                    'epidemic_subtype' => 'plague_bacterial',
                    'severity' => 'pandemic',
                    'spread_vector' => 'Flea bites (Xenopsylla cheopis on rats); secondary pneumonic transmission via respiratory droplets',
                    'societal_responses' => 'Quarantine protocols in Italian city-states; flagellant movements; persecution of Jewish communities; collapse of Church authority',
                    'economic_consequences' => 'Acute labor shortage drove up wages; collapse of long-distance trade networks; abandonment of marginal agricultural land',
                    'date_raw' => '1346 – 1353 CE (major pandemic wave)',
                    'entity_color' => '#2F4F4F',
                ]),
                'source_citations' => json_encode([['source' => 'Benedictow, The Black Death 1346-1353', 'year' => 2004]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $gutenbergId,
                'name' => 'Gutenberg Printing Press',
                'entity_type' => 'event_tech_adoption',
                'entity_group' => 'EVENT',
                'summary' => 'The introduction of movable type printing to Europe by Johannes Gutenberg around 1440, revolutionizing the production of books and the dissemination of knowledge.',
                'significance' => 'Enabled mass production of texts, catalyzing the Renaissance, Reformation, and Scientific Revolution by making knowledge accessible beyond monastic and court elites.',
                'impact_score' => 95,
                'temporal_start' => '1440',
                'temporal_end' => '1455',
                'location_name' => 'Mainz, Holy Roman Empire',
                'wikidata_id' => 'Q124379',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'nlp_approximate',
                'date_confidence' => 'medium',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 9,
                'icon_class' => 'gear',
                'tags' => $this->textArray(['printing', 'gutenberg', 'technology', 'renaissance', 'books']),
                'alternative_names' => $this->textArray(['Movable Type Press', 'Gutenberg Press']),
                'attributes' => json_encode([
                    'acquisition_method' => 'independent_invention',
                    'diffusion_speed' => 'rapid',
                    'impact' => 'Within 50 years of Gutenberg\'s press, over 20 million books printed across Europe; enabled standardization of vernacular languages and undermined the Church\'s monopoly on textual authority',
                    'adaptation_notes' => 'Gutenberg combined existing screw-press technology with oil-based inks and alloy type; first major product was the 42-line Bible (B42) c. 1455',
                    'date_raw' => 'c. 1440 – 1455 CE (development and Gutenberg Bible)',
                    'entity_color' => '#696969',
                ]),
                'source_citations' => json_encode([['source' => 'Eisenstein, The Printing Press as an Agent of Change', 'year' => 1979]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $magnaId,
                'name' => 'Magna Carta',
                'entity_type' => 'event_legal_reform',
                'entity_group' => 'EVENT',
                'summary' => 'A charter of rights agreed to by King John of England at Runnymede in 1215, establishing that the king was subject to law and guaranteeing basic liberties to free men.',
                'significance' => 'Foundational document for constitutional governance, due process, and the rule of law. Directly influenced the U.S. Constitution and the Universal Declaration of Human Rights.',
                'impact_score' => 92,
                'temporal_start' => '1215-06-15',
                'temporal_end' => '1215-06-15',
                'location_name' => 'Runnymede, Surrey, England',
                'wikidata_id' => 'Q131569',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'point',
                'location_confidence' => 'high',
                'location_method' => 'source_database',
                'display_priority' => 9,
                'icon_class' => 'scales',
                'tags' => $this->textArray(['law', 'charter', 'england', 'rights', 'constitutional']),
                'alternative_names' => $this->textArray(['Great Charter', 'Magna Carta Libertatum']),
                'attributes' => json_encode([
                    'reform_subtype' => 'constitutional_change',
                    'provisions' => '63 clauses covering habeas corpus, trial by jury of peers, limits on royal taxation, and freedom of the Church; clause 39 established no free man shall be imprisoned without lawful judgment',
                    'motivation' => 'Baronial revolt against King John\'s arbitrary rule, heavy taxation, and military failures in France',
                    'longevity' => 'Reissued multiple times; three clauses remain statute law in England to this day',
                    'effects_intended' => 'Constrain arbitrary royal power and protect barons\' feudal rights',
                    'effects_unintended' => 'Became the cornerstone of English constitutionalism and individual liberty far beyond its original baronial context',
                    'date_raw' => '15 June 1215',
                    'entity_color' => '#BDB76B',
                ]),
                'source_citations' => json_encode([['source' => 'Holt, Magna Carta', 'year' => 1992]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $migrationId,
                'name' => 'Migration Period',
                'entity_type' => 'migration',
                'entity_group' => 'EVENT',
                'summary' => 'The large-scale movements of Germanic, Slavic, Hunnic, and other peoples into and across Europe from roughly 375 to 568 CE, triggered partly by the Hunnic invasions from Central Asia.',
                'significance' => 'Reshaped the ethnic, linguistic, and political map of Europe, leading to the fall of the Western Roman Empire and the formation of medieval kingdoms.',
                'impact_score' => 88,
                'temporal_start' => '0375',
                'temporal_end' => '0568',
                'location_name' => 'Europe',
                'wikidata_id' => 'Q152036',
                'verification_status' => 'human_verified',
                'confidence' => 'medium',
                'date_method' => 'nlp_approximate',
                'date_confidence' => 'medium',
                'duration_type' => 'period',
                'location_confidence' => 'low',
                'location_method' => 'source_database',
                'display_priority' => 7,
                'icon_class' => 'migration_arrow',
                'tags' => $this->textArray(['migration', 'germanic', 'barbarian', 'late_antiquity', 'roman_fall']),
                'alternative_names' => $this->textArray(['Völkerwanderung', 'Barbarian Invasions']),
                'attributes' => json_encode([
                    'migration_subtype' => 'invasion',
                    'migrating_group' => 'Germanic peoples (Goths, Vandals, Franks, Lombards), Huns, Slavs, and Avars',
                    'voluntary' => false,
                    'impact_origin' => 'Collapse of Hunnic pressure triggered chain displacement of steppe peoples westward',
                    'impact_destination' => 'Dissolution of Western Roman administration; formation of Visigothic, Frankish, Vandal, and Lombard kingdoms across former Roman territory',
                    'date_raw' => 'c. 375 – 568 CE',
                    'entity_color' => '#8FBC8F',
                ]),
                'source_citations' => json_encode([['source' => 'Heather, Empires and Barbarians', 'year' => 2009]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $varnaId,
                'name' => 'Battle of Varna',
                'entity_type' => 'event_battle',
                'entity_group' => 'EVENT',
                'summary' => 'A decisive battle fought on 10 November 1444 near Varna between Ottoman forces under Murad II and a crusader coalition led by Wladyslaw III of Poland-Hungary.',
                'significance' => 'The Ottoman victory ended the major crusading attempt in the Balkans and secured Ottoman strategic dominance before the conquest of Constantinople.',
                'impact_score' => 88,
                'temporal_start' => '1444-11-10',
                'temporal_end' => '1444-11-10',
                'location_name' => 'Varna, Bulgaria',
                'wikidata_id' => 'Q487829',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'point',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 9,
                'icon_class' => 'crossed_swords',
                'tags' => $this->textArray(['ottoman', 'crusade', 'balkans', 'murad_ii', 'varna']),
                'alternative_names' => $this->textArray(['Second Battle of Varna']),
                'attributes' => json_encode([
                    'battle_subtype' => 'field_battle',
                    'outcome' => 'decisive_victory',
                    'victor_side' => 'Ottoman',
                    'date_raw' => '10 November 1444',
                    'entity_color' => '#B22222',
                ]),
                'source_citations' => json_encode([['source' => 'Setton, The Papacy and the Levant', 'year' => 1978]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
        ];
    }

    /**
     * @return list<array<string, mixed>>
     */
    private function economyEntities(mixed $now): array
    {
        // Silk Road
        $silkId = '40000000-0000-0000-0000-000000000001';
        $this->geometries[$silkId] = ['lat' => 39.9042, 'lon' => 76.0];

        // Tin (Bronze Age)
        $tinId = '40000000-0000-0000-0000-000000000002';
        $this->geometries[$tinId] = ['lat' => 50.2660, 'lon' => -5.0527];

        // Roman Denarius
        $denariusId = '40000000-0000-0000-0000-000000000003';
        $this->geometries[$denariusId] = ['lat' => 41.9028, 'lon' => 12.4964];

        // Indian Ocean Trade Network
        $indianOceanId = '40000000-0000-0000-0000-000000000004';
        $this->geometries[$indianOceanId] = ['lat' => 12.0, 'lon' => 65.0];

        return [
            [
                'entity_id' => $silkId,
                'name' => 'Silk Road',
                'entity_type' => 'trade_route',
                'entity_group' => 'ECONOMY',
                'summary' => 'A network of ancient trade routes connecting China and the Far East with the Middle East and Europe, facilitating the exchange of goods, ideas, religions, and technologies.',
                'significance' => 'The primary conduit for cross-civilizational exchange for over 1,500 years, transmitting silk, spices, paper, gunpowder, Buddhism, Islam, and plague across continents.',
                'impact_score' => 94,
                'temporal_start' => '-0130',
                'temporal_end' => '1450',
                'location_name' => 'Eurasia (Chang\'an to Constantinople)',
                'wikidata_id' => 'Q7340',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'nlp_approximate',
                'date_confidence' => 'medium',
                'duration_type' => 'period',
                'location_confidence' => 'medium',
                'location_method' => 'source_database',
                'display_priority' => 9,
                'icon_class' => 'trade_ship',
                'tags' => $this->textArray(['trade', 'silk', 'eurasia', 'caravan', 'exchange']),
                'alternative_names' => $this->textArray(['Seidenstraße', 'Silk Route']),
                'attributes' => json_encode([
                    'route_subtype' => 'mixed',
                    'date_raw' => '130 BCE – c. 1450 CE',
                    'entity_color' => '#B8860B',
                ]),
                'source_citations' => json_encode([['source' => 'Hansen, The Silk Road: A New History', 'year' => 2012]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $tinId,
                'name' => 'Cornish Tin',
                'entity_type' => 'natural_resource',
                'entity_group' => 'ECONOMY',
                'summary' => 'Tin deposits in Cornwall, England, that were among the most significant sources of tin in the ancient world, essential for bronze production.',
                'significance' => 'Cornish tin enabled the Bronze Age across much of Europe and the Mediterranean, creating one of the earliest long-distance trade networks.',
                'impact_score' => 70,
                'temporal_start' => '-2150',
                'temporal_end' => '-0050',
                'location_name' => 'Cornwall, Britain',
                'wikidata_id' => 'Q12638',
                'verification_status' => 'human_verified',
                'confidence' => 'medium',
                'date_method' => 'nlp_approximate',
                'date_confidence' => 'low',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'geonames',
                'display_priority' => 5,
                'icon_class' => 'gem',
                'tags' => $this->textArray(['tin', 'bronze_age', 'mining', 'cornwall', 'trade']),
                'alternative_names' => $this->textArray(['Cassiterides tin', 'Tin Islands']),
                'attributes' => json_encode([
                    'resource_category' => 'metal_strategic',
                    'renewability' => 'finite',
                    'is_tradeable' => true,
                    'substitutability' => 'No direct substitute for tin in bronze alloy; critical strategic bottleneck for Bronze Age polities',
                    'transport_difficulty' => 'High; required long-distance overland and maritime routes from Britain to Mediterranean',
                    'cultural_value' => 'Associated with wealth and military power through bronze weaponry and prestige goods',
                    'date_raw' => 'c. 2150 BCE – 50 BCE (peak ancient extraction)',
                    'entity_color' => '#708090',
                ]),
                'source_citations' => json_encode([['source' => 'Penhallurick, Tin in Antiquity', 'year' => 1986]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $denariusId,
                'name' => 'Roman Denarius',
                'entity_type' => 'currency_monetary_system',
                'entity_group' => 'ECONOMY',
                'summary' => 'The standard silver coin of the Roman Republic and Empire, serving as the backbone of Roman monetary policy for over four centuries.',
                'significance' => 'Facilitated trade across the Roman world and its progressive debasement is often cited as a factor in the economic decline of the Roman Empire.',
                'impact_score' => 75,
                'temporal_start' => '-0211',
                'temporal_end' => '0274',
                'location_name' => 'Roman Republic / Empire',
                'wikidata_id' => 'Q173117',
                'verification_status' => 'human_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'period',
                'location_confidence' => 'medium',
                'location_method' => 'source_database',
                'display_priority' => 6,
                'icon_class' => 'coin',
                'tags' => $this->textArray(['currency', 'roman', 'silver', 'coin', 'money']),
                'alternative_names' => $this->textArray(['Denarii']),
                'attributes' => json_encode([
                    'currency_type' => 'coin_metal',
                    'date_raw' => '211 BCE – 274 CE (replaced by antoninianus)',
                    'entity_color' => '#C0C0C0',
                ]),
                'source_citations' => json_encode([['source' => 'Crawford, Roman Republican Coinage', 'year' => 1974]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $indianOceanId,
                'name' => 'Indian Ocean Trade Network',
                'entity_type' => 'trade_route',
                'entity_group' => 'ECONOMY',
                'summary' => 'A maritime trade system spanning the Indian Ocean, connecting East Africa, Arabia, Persia, India, and Southeast Asia through monsoon-driven sea routes from at least the 1st century BCE.',
                'significance' => 'Predated and outlasted the Silk Road as a channel for spices, textiles, ivory, and gold, shaping the spread of Islam, Hinduism, and Buddhism across the Indian Ocean rim.',
                'impact_score' => 88,
                'temporal_start' => '-0100',
                'temporal_end' => '1500',
                'location_name' => 'Indian Ocean (Africa–Arabia–India–Southeast Asia)',
                'wikidata_id' => 'Q1061967',
                'verification_status' => 'human_verified',
                'confidence' => 'high',
                'date_method' => 'nlp_approximate',
                'date_confidence' => 'medium',
                'duration_type' => 'period',
                'location_confidence' => 'medium',
                'location_method' => 'source_database',
                'display_priority' => 8,
                'icon_class' => 'trade_ship',
                'tags' => $this->textArray(['trade', 'maritime', 'indian_ocean', 'monsoon', 'spice']),
                'alternative_names' => $this->textArray(['Maritime Silk Road', 'Spice Route']),
                'attributes' => json_encode([
                    'route_subtype' => 'maritime',
                    'date_raw' => 'c. 100 BCE – 1500 CE',
                    'entity_color' => '#1E90FF',
                ]),
                'source_citations' => json_encode([['source' => 'Sheriff, Dhow Cultures of the Indian Ocean', 'year' => 2010]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
        ];
    }

    /**
     * @return list<array<string, mixed>>
     */
    private function cultureEntities(mixed $now): array
    {
        // Iliad
        $iliadId = '50000000-0000-0000-0000-000000000001';
        $this->geometries[$iliadId] = ['lat' => 39.9574, 'lon' => 26.2389];

        // Renaissance
        $renaissanceId = '50000000-0000-0000-0000-000000000002';
        $this->geometries[$renaissanceId] = ['lat' => 43.7696, 'lon' => 11.2558];

        // Linear B
        $linearBId = '50000000-0000-0000-0000-000000000003';
        $this->geometries[$linearBId] = ['lat' => 35.2981, 'lon' => 25.1631];

        // Quran
        $quranId = '50000000-0000-0000-0000-000000000004';
        $this->geometries[$quranId] = ['lat' => 21.4225, 'lon' => 39.8262];

        // Code of Hammurabi
        $hammuId = '50000000-0000-0000-0000-000000000005';
        $this->geometries[$hammuId] = ['lat' => 32.5422, 'lon' => 44.4209];

        // Protestant Reformation
        $reformId = '50000000-0000-0000-0000-000000000006';
        $this->geometries[$reformId] = ['lat' => 51.8660, 'lon' => 11.6267];

        // Compass
        $compassId = '50000000-0000-0000-0000-000000000007';
        $this->geometries[$compassId] = ['lat' => 34.2658, 'lon' => 108.9541];

        // Histories of Herodotus
        $herodotusId = '50000000-0000-0000-0000-000000000008';
        $this->geometries[$herodotusId] = ['lat' => 37.0382, 'lon' => 27.4241];

        return [
            [
                'entity_id' => $iliadId,
                'name' => 'The Iliad',
                'entity_type' => 'cultural_work',
                'entity_group' => 'CULTURE',
                'summary' => 'An ancient Greek epic poem attributed to Homer, set during the Trojan War and focusing on the wrath of Achilles. Composed in dactylic hexameter, it is one of the oldest works of Western literature.',
                'significance' => 'Foundational text of Western literature, shaping Greek identity, education, and artistic expression for millennia.',
                'impact_score' => 93,
                'temporal_start' => '-0750',
                'temporal_end' => '-0700',
                'location_name' => 'Ionia (western Anatolia)',
                'wikidata_id' => 'Q8275',
                'verification_status' => 'expert_verified',
                'confidence' => 'medium',
                'date_method' => 'nlp_approximate',
                'date_confidence' => 'low',
                'duration_type' => 'uncertain',
                'location_confidence' => 'low',
                'location_method' => 'llm_disambiguation',
                'display_priority' => 9,
                'icon_class' => 'scroll',
                'tags' => $this->textArray(['epic', 'homer', 'trojan_war', 'greek', 'literature']),
                'alternative_names' => $this->textArray(['Ἰλιάς', 'Ilias']),
                'attributes' => json_encode([
                    'work_subtype' => 'literary_text',
                    'style_genre' => 'Epic poetry in dactylic hexameter; oral tradition crystallised into written form',
                    'preservation_status' => 'extant',
                    'current_location' => 'Preserved in manuscripts; oldest near-complete MSS from 10th century CE (Venetus A, Venice)',
                    'influence_description' => 'Canonical educational text throughout antiquity; model for Virgil\'s Aeneid; continues to shape Western literature, film, and philosophy',
                    'date_raw' => 'c. 750–700 BCE (composition)',
                    'entity_color' => '#8B4513',
                ]),
                'source_citations' => json_encode([['source' => 'Kirk, The Iliad: A Commentary', 'year' => 1985]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $renaissanceId,
                'name' => 'Renaissance',
                'entity_type' => 'intellectual_movement',
                'entity_group' => 'CULTURE',
                'summary' => 'A cultural, artistic, and intellectual movement that began in Italy in the 14th century and spread across Europe, characterized by renewed interest in classical antiquity and humanism.',
                'significance' => 'Transformed European art, philosophy, science, and politics, bridging the medieval and modern worlds and laying the intellectual foundations for the Enlightenment.',
                'impact_score' => 96,
                'temporal_start' => '1350',
                'temporal_end' => '1600',
                'location_name' => 'Florence, Italy (origin)',
                'wikidata_id' => 'Q4692',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'nlp_approximate',
                'date_confidence' => 'medium',
                'duration_type' => 'period',
                'location_confidence' => 'medium',
                'location_method' => 'source_database',
                'display_priority' => 10,
                'icon_class' => 'palette',
                'tags' => $this->textArray(['renaissance', 'humanism', 'art', 'italy', 'rebirth']),
                'alternative_names' => $this->textArray(['Rinascimento']),
                'attributes' => json_encode([
                    'intellectual_movement_subtype' => 'artistic_style',
                    'core_ideas' => 'Revival of Greco-Roman classical learning; humanism placing mankind at the centre of inquiry; naturalism in art and empirical observation',
                    'methodology' => 'Direct study of ancient texts and artefacts; perspective and proportion in visual arts; vernacular literature alongside Latin scholarship',
                    'style_characteristics' => 'Linear perspective, chiaroscuro, anatomical realism in painting and sculpture; Petrarchan sonnet in literature; Ciceronian Latin in prose',
                    'date_raw' => 'c. 1350 – 1600 CE',
                    'entity_color' => '#FFD700',
                ]),
                'source_citations' => json_encode([['source' => 'Burckhardt, The Civilization of the Renaissance in Italy', 'year' => 1860]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $linearBId,
                'name' => 'Linear B',
                'entity_type' => 'language',
                'entity_group' => 'CULTURE',
                'summary' => 'A syllabic script used for writing Mycenaean Greek, the earliest attested form of Greek. Deciphered by Michael Ventris in 1952.',
                'significance' => 'Pushed back the known history of the Greek language by several centuries and revealed the bureaucratic complexity of Mycenaean palace economies.',
                'impact_score' => 72,
                'temporal_start' => '-1450',
                'temporal_end' => '-1200',
                'location_name' => 'Knossos, Crete / Pylos, Greece',
                'wikidata_id' => 'Q189046',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'nlp_approximate',
                'date_confidence' => 'medium',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'pleiades',
                'display_priority' => 6,
                'icon_class' => 'language_glyph',
                'tags' => $this->textArray(['script', 'mycenaean', 'greek', 'bronze_age', 'decipherment']),
                'alternative_names' => $this->textArray(['Mycenaean script']),
                'attributes' => json_encode([
                    'language_family' => 'Indo-European, Hellenic',
                    'language_status' => 'extinct',
                    'writing_system' => 'Syllabic script (87 signs); adapted from Minoan Linear A which remains undeciphered',
                    'iso_639_code' => null,
                    'date_raw' => 'c. 1450 – 1200 BCE',
                    'entity_color' => '#D2691E',
                ]),
                'source_citations' => json_encode([['source' => 'Chadwick, The Decipherment of Linear B', 'year' => 1958]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $quranId,
                'name' => 'The Quran',
                'entity_type' => 'religious_text',
                'entity_group' => 'CULTURE',
                'summary' => 'The central religious text of Islam, believed by Muslims to be the verbatim word of God as revealed to the Prophet Muhammad over approximately 23 years.',
                'significance' => 'Foundational text of Islamic civilization, shaping law, governance, art, literature, and daily life for over 1.8 billion people worldwide.',
                'impact_score' => 97,
                'temporal_start' => '0609',
                'temporal_end' => '0632',
                'location_name' => 'Mecca and Medina, Arabia',
                'wikidata_id' => 'Q428',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 10,
                'icon_class' => 'sacred_book',
                'tags' => $this->textArray(['islam', 'quran', 'scripture', 'arabic', 'revelation']),
                'alternative_names' => $this->textArray(['القرآن', 'Al-Quran', 'Koran']),
                'attributes' => json_encode([
                    'text_type' => 'scripture',
                    'composition_date' => '609–632 CE; standardised under Caliph Uthman c. 650 CE',
                    'genre' => 'prophecy',
                    'material' => 'Oral recitation; early written on parchment, bone, and palm leaves; codified in written mushaf form',
                    'date_raw' => '609 – 632 CE (period of revelation)',
                    'entity_color' => '#006400',
                ]),
                'source_citations' => json_encode([['source' => 'Neuwirth, The Quran in Context', 'year' => 2010]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $hammuId,
                'name' => 'Code of Hammurabi',
                'entity_type' => 'legal_code',
                'entity_group' => 'CULTURE',
                'summary' => 'One of the oldest deciphered writings of significant length in the world, this Babylonian code of law was enacted by King Hammurabi of Babylon around 1754 BCE.',
                'significance' => 'Among the earliest and most complete legal codes, establishing the principle of codified law and including early concepts of presumption of innocence and evidence-based judgment.',
                'impact_score' => 88,
                'temporal_start' => '-1754',
                'temporal_end' => '-1754',
                'location_name' => 'Babylon, Mesopotamia',
                'wikidata_id' => 'Q37517',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'medium',
                'duration_type' => 'point',
                'location_confidence' => 'high',
                'location_method' => 'pleiades',
                'display_priority' => 8,
                'icon_class' => 'scales',
                'tags' => $this->textArray(['law', 'babylon', 'mesopotamia', 'hammurabi', 'ancient']),
                'alternative_names' => $this->textArray(['Codex Hammurabi']),
                'attributes' => json_encode([
                    'promulgation_date' => 'c. 1754 BCE under Hammurabi, sixth king of the First Babylonian dynasty',
                    'legal_philosophy' => 'Lex talionis (proportional retribution); hierarchical penalties based on social class; commercial and family law provisions',
                    'enforcement_duration' => 'Remained authoritative reference throughout the Old Babylonian period; copied as scribal exercise for over a millennium',
                    'modern_significance' => 'Earliest near-complete law code; foundational example of written codification; displayed in the Louvre, Paris',
                    'date_raw' => 'c. 1754 BCE',
                    'entity_color' => '#D2B48C',
                ]),
                'source_citations' => json_encode([['source' => 'Roth, Law Collections from Mesopotamia and Asia Minor', 'year' => 1997]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $reformId,
                'name' => 'Protestant Reformation',
                'entity_type' => 'religious_movement',
                'entity_group' => 'CULTURE',
                'summary' => 'A major 16th-century movement within Western Christianity initiated by Martin Luther\'s Ninety-five Theses in 1517, challenging papal authority and key Catholic doctrines.',
                'significance' => 'Split Western Christendom into Catholic and Protestant traditions, triggering the Wars of Religion, fostering literacy through vernacular Bibles, and reshaping European politics.',
                'impact_score' => 93,
                'temporal_start' => '1517',
                'temporal_end' => '1648',
                'location_name' => 'Wittenberg, Saxony',
                'wikidata_id' => 'Q12539',
                'verification_status' => 'expert_verified',
                'confidence' => 'high',
                'date_method' => 'source_database',
                'date_confidence' => 'high',
                'duration_type' => 'period',
                'location_confidence' => 'high',
                'location_method' => 'wikidata',
                'display_priority' => 9,
                'icon_class' => 'temple',
                'tags' => $this->textArray(['reformation', 'protestant', 'luther', 'religion', 'christianity']),
                'alternative_names' => $this->textArray(['Reformation', 'Lutheran Reformation']),
                'attributes' => json_encode([
                    'movement_subtype' => 'reform_movement',
                    'core_doctrines' => 'Sola scriptura (Scripture alone), sola fide (faith alone), sola gratia (grace alone); rejection of papal infallibility and indulgences; priesthood of all believers',
                    'institutional_structure' => 'Decentralised; Lutheran state churches in Germany and Scandinavia; Calvinist presbyteries in Switzerland, France, Scotland; Anglican church under royal supremacy in England',
                    'date_raw' => '1517 – 1648 CE (Ninety-five Theses to Westphalia)',
                    'entity_color' => '#A0522D',
                ]),
                'source_citations' => json_encode([['source' => 'MacCulloch, The Reformation', 'year' => 2003]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $compassId,
                'name' => 'Magnetic Compass',
                'entity_type' => 'technology',
                'entity_group' => 'CULTURE',
                'summary' => 'A navigational instrument using a magnetized needle pointing to magnetic north, first developed in China during the Han dynasty for divination before being adapted for navigation.',
                'significance' => 'Revolutionized maritime navigation, enabling the Age of Exploration, long-distance trade, and global colonization patterns.',
                'impact_score' => 89,
                'temporal_start' => '0206',
                'temporal_end' => '1300',
                'location_name' => 'China (origin)',
                'wikidata_id' => 'Q204520',
                'verification_status' => 'human_verified',
                'confidence' => 'medium',
                'date_method' => 'nlp_approximate',
                'date_confidence' => 'low',
                'duration_type' => 'period',
                'location_confidence' => 'medium',
                'location_method' => 'source_database',
                'display_priority' => 7,
                'icon_class' => 'lightbulb',
                'tags' => $this->textArray(['navigation', 'compass', 'china', 'technology', 'invention']),
                'alternative_names' => $this->textArray(['South-pointing needle', 'Sīnán']),
                'attributes' => json_encode([
                    'tech_domain' => 'navigation',
                    'impact_description' => 'Enabled reliable open-ocean sailing independent of stars and coastlines; adopted in Europe via Arab intermediaries c. 12th century CE; directly enabled Portuguese and Iberian Age of Discovery',
                    'date_raw' => 'c. 206 BCE (divination) – 1300 CE (widespread navigation)',
                    'entity_color' => '#CD853F',
                ]),
                'source_citations' => json_encode([['source' => 'Needham, Science and Civilisation in China, Vol. 4', 'year' => 1962]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'entity_id' => $herodotusId,
                'name' => 'Histories of Herodotus',
                'entity_type' => 'cultural_work',
                'entity_group' => 'CULTURE',
                'summary' => 'A prose narrative composed by Herodotus of Halicarnassus around 440 BCE, recounting the origins and course of the Greco-Persian Wars alongside ethnographic descriptions of the known world.',
                'significance' => 'Widely regarded as the founding text of Western historiography; introduced systematic inquiry (historia) as a method for understanding past events and foreign cultures.',
                'impact_score' => 90,
                'temporal_start' => '-0450',
                'temporal_end' => '-0420',
                'location_name' => 'Halicarnassus (Bodrum, Turkey)',
                'wikidata_id' => 'Q165800',
                'verification_status' => 'expert_verified',
                'confidence' => 'medium',
                'date_method' => 'nlp_approximate',
                'date_confidence' => 'medium',
                'duration_type' => 'uncertain',
                'location_confidence' => 'medium',
                'location_method' => 'pleiades',
                'display_priority' => 8,
                'icon_class' => 'scroll',
                'tags' => $this->textArray(['history', 'herodotus', 'greek', 'historiography', 'persian_wars']),
                'alternative_names' => $this->textArray(['Ἱστορίαι', 'The Histories']),
                'attributes' => json_encode([
                    'work_subtype' => 'historical_text',
                    'style_genre' => 'Prose narrative history in Ionic Greek; combines political, military, ethnographic, and geographic inquiry',
                    'preservation_status' => 'extant',
                    'current_location' => 'Preserved in medieval manuscripts; critical edition by Hude (Oxford Classical Texts)',
                    'influence_description' => 'Founded the Western historical tradition; influenced Thucydides and all subsequent historians; primary source for the Greco-Persian Wars',
                    'date_raw' => 'c. 450–420 BCE (composition)',
                    'entity_color' => '#8B7355',
                ]),
                'source_citations' => json_encode([['source' => 'Herodotus, Histories (trans. Godley, Loeb Classical Library)', 'year' => -440]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
        ];
    }
}
