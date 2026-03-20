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

            DB::table('entities')->insert($entity);

            // Add point geometry if defined
            if (isset($this->geometries[$id])) {
                $coords = $this->geometries[$id];
                DB::statement(
                    "UPDATE entities SET geom = ST_SetSRID(ST_MakePoint(?, ?), 4326) WHERE entity_id = ?",
                    [$coords['lon'], $coords['lat'], $id],
                );
            }

            // Add territory polygon if defined
            if (isset($this->territories[$id])) {
                DB::statement(
                    "UPDATE entities SET territory_geom = ST_SetSRID(ST_GeomFromGeoJSON(?), 4326) WHERE entity_id = ?",
                    [$this->territories[$id], $id],
                );
            }
        }

        // Derive integer year columns from text temporal values
        DB::statement("
            UPDATE entities
            SET temporal_start_year = CAST(SUBSTRING(temporal_start FROM '^-?\\d+') AS integer)
            WHERE temporal_start IS NOT NULL
              AND temporal_start ~ '^-?\\d+'
              AND temporal_start_year IS NULL
        ");
        DB::statement("
            UPDATE entities
            SET temporal_end_year = CAST(SUBSTRING(temporal_end FROM '^-?\\d+') AS integer)
            WHERE temporal_end IS NOT NULL
              AND temporal_end ~ '^-?\\d+'
              AND temporal_end_year IS NULL
        ");
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
            'coordinates' => [[[- 9.5, 36.0], [35.0, 36.0], [35.0, 55.0], [-9.5, 55.0], [-9.5, 36.0]]],
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

        // Julius Caesar
        $caesarId = '10000000-0000-0000-0000-000000000004';
        $this->geometries[$caesarId] = ['lat' => 41.9028, 'lon' => 12.4964];

        // Genghis Khan
        $genghisId = '10000000-0000-0000-0000-000000000005';
        $this->geometries[$genghisId] = ['lat' => 47.9185, 'lon' => 106.9177];

        // Praetorian Guard
        $praetorianId = '10000000-0000-0000-0000-000000000006';
        $this->geometries[$praetorianId] = ['lat' => 41.9028, 'lon' => 12.4964];

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
                'date_raw' => '27 BCE – 476 CE',
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
                'entity_color' => '#8B0000',
                'tags' => $this->textArray(['empire', 'rome', 'ancient', 'mediterranean', 'latin']),
                'alternative_names' => $this->textArray(['Imperium Romanum', 'SPQR']),
                'attributes' => json_encode(['capital' => 'Rome', 'government_type' => 'autocracy', 'peak_population' => '70 million']),
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
                'date_raw' => '1299 – 1922 CE',
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
                'entity_color' => '#006400',
                'tags' => $this->textArray(['empire', 'ottoman', 'islamic', 'anatolia', 'balkans']),
                'alternative_names' => $this->textArray(['Devlet-i ʿAliyye-i ʿOsmâniyye', 'Sublime Ottoman State']),
                'attributes' => json_encode(['capital' => 'Constantinople', 'government_type' => 'absolute monarchy', 'peak_population' => '35 million']),
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
                'date_raw' => '305 BCE – 30 BCE',
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
                'entity_color' => '#DAA520',
                'tags' => $this->textArray(['dynasty', 'hellenistic', 'egypt', 'ptolemy', 'macedonian']),
                'alternative_names' => $this->textArray(['Ptolemies', 'Lagid dynasty']),
                'attributes' => json_encode(['founder' => 'Ptolemy I Soter', 'last_ruler' => 'Cleopatra VII']),
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
                'date_raw' => '100 BCE – 44 BCE (Ides of March)',
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
                'entity_color' => '#800020',
                'tags' => $this->textArray(['roman', 'dictator', 'general', 'politician', 'assassination']),
                'alternative_names' => $this->textArray(['Caesar', 'Divus Iulius']),
                'attributes' => json_encode(['birth_place' => 'Rome', 'cause_of_death' => 'assassination', 'offices' => ['consul', 'dictator perpetuo']]),
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
                'date_raw' => 'c. 1162 – 1227 CE',
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
                'entity_color' => '#4B3621',
                'tags' => $this->textArray(['mongol', 'khan', 'conqueror', 'steppe', 'empire']),
                'alternative_names' => $this->textArray(['Temüjin', 'Chinggis Khaan']),
                'attributes' => json_encode(['birth_name' => 'Temüjin', 'title' => 'Khagan']),
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
                'date_raw' => '27 BCE – 312 CE',
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
                'entity_color' => '#B22222',
                'tags' => $this->textArray(['roman', 'military', 'guard', 'praetorian', 'elite']),
                'alternative_names' => $this->textArray(['Cohortes Praetoriae']),
                'attributes' => json_encode(['max_strength' => 10000, 'disbanded_by' => 'Constantine I']),
                'source_citations' => json_encode([['source' => 'Bingham, The Praetorian Guard', 'year' => 2013]]),
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
                'date_raw' => '330 CE – 1453 CE (fall to Ottomans)',
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
                'entity_color' => '#4B0082',
                'tags' => $this->textArray(['byzantine', 'city', 'capital', 'trade', 'orthodox']),
                'alternative_names' => $this->textArray(['Byzantium', 'Istanbul', 'Nova Roma', 'Tsargrad']),
                'attributes' => json_encode(['peak_population' => '500,000', 'notable_structures' => ['Hagia Sophia', 'Hippodrome', 'Theodosian Walls']]),
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
                'summary' => 'A series of fortifications made of stone, brick, tamped earth, and other materials, built along the northern borders of China to protect against various nomadic groups.',
                'significance' => 'The most extensive construction project in human history, representing centuries of Chinese defensive strategy and labor mobilization.',
                'impact_score' => 90,
                'temporal_start' => '-0700',
                'temporal_end' => '1644',
                'date_raw' => '7th century BCE – 1644 CE',
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
                'entity_color' => '#808080',
                'tags' => $this->textArray(['china', 'wall', 'fortification', 'defense', 'monument']),
                'alternative_names' => $this->textArray(['Wànlǐ Chángchéng', 'Long Wall']),
                'attributes' => json_encode(['total_length_km' => 21196, 'unesco' => true]),
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
                'date_raw' => '6th century BCE – 1st century BCE',
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
                'entity_color' => '#C0C0C0',
                'tags' => $this->textArray(['mining', 'silver', 'athens', 'economy', 'ancient_greece']),
                'alternative_names' => $this->textArray(['Lavrion', 'Laurium']),
                'attributes' => json_encode(['mineral' => 'silver-lead', 'workforce' => 'enslaved labor']),
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
                'date_raw' => '1088 CE – present',
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
                'entity_color' => '#8B4513',
                'tags' => $this->textArray(['university', 'education', 'medieval', 'law', 'italy']),
                'alternative_names' => $this->textArray(['Alma Mater Studiorum', 'Universitas Bononiensis']),
                'attributes' => json_encode(['specialization' => 'Roman law', 'notable_alumni' => ['Petrarch', 'Copernicus', 'Dante']]),
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
                'date_raw' => 'c. 1113 – 1150 CE (construction period)',
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
                'entity_color' => '#DAA520',
                'tags' => $this->textArray(['khmer', 'temple', 'cambodia', 'hindu', 'buddhist']),
                'alternative_names' => $this->textArray(['Nokor Wat', 'City Temple']),
                'attributes' => json_encode(['commissioned_by' => 'Suryavarman II', 'area_hectares' => 162, 'unesco' => true]),
                'source_citations' => json_encode([['source' => 'Higham, The Civilization of Angkor', 'year' => 2001]]),
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
                'date_raw' => '6 April – 29 May 1453',
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
                'entity_color' => '#DC143C',
                'tags' => $this->textArray(['byzantine', 'ottoman', 'siege', 'constantinople', '1453']),
                'alternative_names' => $this->textArray(['Siege of Constantinople', 'Conquest of Constantinople']),
                'attributes' => json_encode(['attacker' => 'Ottoman Empire', 'defender' => 'Byzantine Empire', 'commander_attack' => 'Mehmed II', 'commander_defense' => 'Constantine XI']),
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
                'summary' => 'A series of armed conflicts between the kingdoms of England and France from 1337 to 1453, rooted in disputes over the French crown.',
                'significance' => 'Transformed medieval warfare, fostered national identities in both England and France, and saw the emergence of standing armies and gunpowder weapons in Europe.',
                'impact_score' => 86,
                'temporal_start' => '1337',
                'temporal_end' => '1453',
                'date_raw' => '1337 – 1453 CE',
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
                'entity_color' => '#4169E1',
                'tags' => $this->textArray(['war', 'medieval', 'england', 'france', 'chivalry']),
                'alternative_names' => $this->textArray(['Guerre de Cent Ans']),
                'attributes' => json_encode(['belligerents' => ['England', 'France'], 'key_battles' => ['Crécy', 'Poitiers', 'Agincourt', 'Orléans']]),
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
                'date_raw' => 'August 480 BCE (3 days)',
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
                'entity_color' => '#8B0000',
                'tags' => $this->textArray(['sparta', 'persia', 'battle', 'greco-persian_wars', 'leonidas']),
                'alternative_names' => $this->textArray(['Thermopylai', 'Hot Gates']),
                'attributes' => json_encode(['greek_commander' => 'Leonidas I', 'persian_commander' => 'Xerxes I', 'greek_forces' => '7,000', 'persian_forces' => '100,000–300,000']),
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
                'date_raw' => '15 May – 24 October 1648',
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
                'entity_color' => '#556B2F',
                'tags' => $this->textArray(['treaty', 'sovereignty', 'westphalia', 'thirty_years_war', 'international_law']),
                'alternative_names' => $this->textArray(['Westfälischer Friede', 'Pax Westphalica']),
                'attributes' => json_encode(['treaties' => ['Treaty of Münster', 'Treaty of Osnabrück'], 'wars_ended' => ['Thirty Years\' War', 'Eighty Years\' War']]),
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
                'date_raw' => '1346 – 1353 CE (major pandemic wave)',
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
                'entity_color' => '#2F4F4F',
                'tags' => $this->textArray(['plague', 'pandemic', 'medieval', 'death', 'yersinia_pestis']),
                'alternative_names' => $this->textArray(['Great Pestilence', 'Great Mortality', 'Pestilencia']),
                'attributes' => json_encode(['pathogen' => 'Yersinia pestis', 'estimated_deaths' => '75–200 million', 'mortality_rate_europe' => '30–60%']),
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
                'date_raw' => 'c. 1440 – 1455 CE (development and Gutenberg Bible)',
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
                'entity_color' => '#696969',
                'tags' => $this->textArray(['printing', 'gutenberg', 'technology', 'renaissance', 'books']),
                'alternative_names' => $this->textArray(['Movable Type Press', 'Gutenberg Press']),
                'attributes' => json_encode(['inventor' => 'Johannes Gutenberg', 'first_major_work' => 'Gutenberg Bible (B42)', 'copies_printed' => 180]),
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
                'date_raw' => '15 June 1215',
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
                'entity_color' => '#BDB76B',
                'tags' => $this->textArray(['law', 'charter', 'england', 'rights', 'constitutional']),
                'alternative_names' => $this->textArray(['Great Charter', 'Magna Carta Libertatum']),
                'attributes' => json_encode(['signatories' => ['King John', 'English barons'], 'clauses' => 63, 'surviving_copies' => 4]),
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
                'summary' => 'The large-scale movements of Germanic, Slavic, Hunnic, and other peoples into and across Europe from roughly 375 to 568 CE, triggered partly by the Hunnic invasions.',
                'significance' => 'Reshaped the ethnic, linguistic, and political map of Europe, leading to the fall of the Western Roman Empire and the formation of medieval kingdoms.',
                'impact_score' => 88,
                'temporal_start' => '0375',
                'temporal_end' => '0568',
                'date_raw' => 'c. 375 – 568 CE',
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
                'entity_color' => '#8FBC8F',
                'tags' => $this->textArray(['migration', 'germanic', 'barbarian', 'late_antiquity', 'roman_fall']),
                'alternative_names' => $this->textArray(['Völkerwanderung', 'Barbarian Invasions']),
                'attributes' => json_encode(['major_groups' => ['Goths', 'Vandals', 'Huns', 'Franks', 'Lombards', 'Angles', 'Saxons']]),
                'source_citations' => json_encode([['source' => 'Heather, Empires and Barbarians', 'year' => 2009]]),
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
                'date_raw' => '130 BCE – c. 1450 CE',
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
                'entity_color' => '#B8860B',
                'tags' => $this->textArray(['trade', 'silk', 'eurasia', 'caravan', 'exchange']),
                'alternative_names' => $this->textArray(['Seidenstraße', 'Silk Route']),
                'attributes' => json_encode(['length_km' => 6400, 'key_goods' => ['silk', 'spices', 'precious metals', 'paper', 'gunpowder']]),
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
                'date_raw' => 'c. 2150 BCE – 50 BCE (peak ancient extraction)',
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
                'entity_color' => '#708090',
                'tags' => $this->textArray(['tin', 'bronze_age', 'mining', 'cornwall', 'trade']),
                'alternative_names' => $this->textArray(['Cassiterides tin', 'Tin Islands']),
                'attributes' => json_encode(['mineral' => 'cassiterite', 'use' => 'bronze alloy production']),
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
                'date_raw' => '211 BCE – 274 CE (replaced by antoninianus)',
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
                'entity_color' => '#C0C0C0',
                'tags' => $this->textArray(['currency', 'roman', 'silver', 'coin', 'money']),
                'alternative_names' => $this->textArray(['Denarii']),
                'attributes' => json_encode(['metal' => 'silver', 'initial_weight_grams' => 4.5, 'initial_purity_percent' => 95]),
                'source_citations' => json_encode([['source' => 'Crawford, Roman Republican Coinage', 'year' => 1974]]),
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
                'date_raw' => 'c. 750–700 BCE (composition)',
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
                'entity_color' => '#8B4513',
                'tags' => $this->textArray(['epic', 'homer', 'trojan_war', 'greek', 'literature']),
                'alternative_names' => $this->textArray(['Ἰλιάς', 'Ilias']),
                'attributes' => json_encode(['author' => 'Homer (attributed)', 'lines' => 15693, 'books' => 24, 'language' => 'Ancient Greek']),
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
                'date_raw' => 'c. 1350 – 1600 CE',
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
                'entity_color' => '#FFD700',
                'tags' => $this->textArray(['renaissance', 'humanism', 'art', 'italy', 'rebirth']),
                'alternative_names' => $this->textArray(['Rinascimento']),
                'attributes' => json_encode(['key_figures' => ['Leonardo da Vinci', 'Michelangelo', 'Petrarch', 'Machiavelli'], 'origin_city' => 'Florence']),
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
                'date_raw' => 'c. 1450 – 1200 BCE',
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
                'entity_color' => '#D2691E',
                'tags' => $this->textArray(['script', 'mycenaean', 'greek', 'bronze_age', 'decipherment']),
                'alternative_names' => $this->textArray(['Mycenaean script']),
                'attributes' => json_encode(['type' => 'syllabary', 'signs' => 87, 'deciphered_by' => 'Michael Ventris', 'decipherment_year' => 1952]),
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
                'date_raw' => '609 – 632 CE (period of revelation)',
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
                'entity_color' => '#006400',
                'tags' => $this->textArray(['islam', 'quran', 'scripture', 'arabic', 'revelation']),
                'alternative_names' => $this->textArray(['القرآن', 'Al-Quran', 'Koran']),
                'attributes' => json_encode(['chapters' => 114, 'verses' => 6236, 'language' => 'Classical Arabic']),
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
                'date_raw' => 'c. 1754 BCE',
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
                'entity_color' => '#D2B48C',
                'tags' => $this->textArray(['law', 'babylon', 'mesopotamia', 'hammurabi', 'ancient']),
                'alternative_names' => $this->textArray(['Codex Hammurabi']),
                'attributes' => json_encode(['laws' => 282, 'medium' => 'basalt stele', 'current_location' => 'Louvre Museum, Paris']),
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
                'date_raw' => '1517 – 1648 CE (Ninety-five Theses to Westphalia)',
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
                'entity_color' => '#A0522D',
                'tags' => $this->textArray(['reformation', 'protestant', 'luther', 'religion', 'christianity']),
                'alternative_names' => $this->textArray(['Reformation', 'Lutheran Reformation']),
                'attributes' => json_encode(['initiator' => 'Martin Luther', 'key_figures' => ['John Calvin', 'Huldrych Zwingli', 'Henry VIII'], 'trigger_document' => 'Ninety-five Theses']),
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
                'date_raw' => 'c. 206 BCE (divination) – 1300 CE (widespread navigation)',
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
                'entity_color' => '#CD853F',
                'tags' => $this->textArray(['navigation', 'compass', 'china', 'technology', 'invention']),
                'alternative_names' => $this->textArray(['South-pointing needle', 'Sīnán']),
                'attributes' => json_encode(['origin' => 'Han Dynasty China', 'principle' => 'magnetic polarity', 'first_maritime_use' => 'Song Dynasty (c. 1040 CE)']),
                'source_citations' => json_encode([['source' => 'Needham, Science and Civilisation in China, Vol. 4', 'year' => 1962]]),
                'created_by' => 'seeder',
                'created_at' => $now,
                'updated_at' => $now,
            ],
        ];
    }
}
