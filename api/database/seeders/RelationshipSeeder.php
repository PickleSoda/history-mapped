<?php

declare(strict_types=1);

namespace Database\Seeders;

use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\DB;
use RuntimeException;

/**
 * Seeds the relationships table with curated historical connections.
 *
 * Uses stable UUIDs from EntitySeeder so the seeder is idempotent with
 * a fresh migration.  Uses raw DB::table()->insert() with PG enum casts
 * for relationship_type and confidence_level (same approach as EntitySeeder).
 *
 * Groups:
 *   - Genghis Khan & the Mongol world (dense cluster)
 *   - Roman / Byzantine network
 *   - Events & their causal web
 *   - Economy & trade links
 *   - Culture & knowledge links
 */
class RelationshipSeeder extends Seeder
{
    // ── Entity IDs (mirror EntitySeeder) ─────────────────────────────────────

    // Polity
    private const ROMAN = '10000000-0000-0000-0000-000000000001';

    private const OTTOMAN = '10000000-0000-0000-0000-000000000002';

    private const PTOLEMY = '10000000-0000-0000-0000-000000000003';

    private const CAESAR = '10000000-0000-0000-0000-000000000004';

    private const GENGHIS = '10000000-0000-0000-0000-000000000005';

    private const PRAETORIAN = '10000000-0000-0000-0000-000000000006';

    private const MONGOL = '10000000-0000-0000-0000-000000000007';

    private const BYZANTINE = '10000000-0000-0000-0000-000000000008';

    private const MEHMED_II = '10000000-0000-0000-0000-000000000009';

    private const CONSTANTINE_XI = '10000000-0000-0000-0000-000000000010';

    private const MURAD_II = '10000000-0000-0000-0000-000000000011';

    // Place
    private const CONSTANTINOPLE = '20000000-0000-0000-0000-000000000001';

    private const GREAT_WALL = '20000000-0000-0000-0000-000000000002';

    private const LAURION = '20000000-0000-0000-0000-000000000003';

    private const BOLOGNA = '20000000-0000-0000-0000-000000000004';

    private const ANGKOR = '20000000-0000-0000-0000-000000000005';

    private const ALEXANDRIA = '20000000-0000-0000-0000-000000000006';

    private const EDIRNE = '20000000-0000-0000-0000-000000000007';

    // Event
    private const FALL_CONST = '30000000-0000-0000-0000-000000000001';

    private const HUNDRED_YRS = '30000000-0000-0000-0000-000000000002';

    private const THERMOPYLAE = '30000000-0000-0000-0000-000000000003';

    private const WESTPHALIA = '30000000-0000-0000-0000-000000000004';

    private const PLAGUE = '30000000-0000-0000-0000-000000000005';

    private const GUTENBERG = '30000000-0000-0000-0000-000000000006';

    private const MAGNA_CARTA = '30000000-0000-0000-0000-000000000007';

    private const MIGRATION = '30000000-0000-0000-0000-000000000008';

    private const VARNA = '30000000-0000-0000-0000-000000000009';

    // Economy
    private const SILK_ROAD = '40000000-0000-0000-0000-000000000001';

    private const CORNISH_TIN = '40000000-0000-0000-0000-000000000002';

    private const DENARIUS = '40000000-0000-0000-0000-000000000003';

    private const INDIAN_OCEAN = '40000000-0000-0000-0000-000000000004';

    // Culture
    private const ILIAD = '50000000-0000-0000-0000-000000000001';

    private const RENAISSANCE = '50000000-0000-0000-0000-000000000002';

    private const LINEAR_B = '50000000-0000-0000-0000-000000000003';

    private const QURAN = '50000000-0000-0000-0000-000000000004';

    private const HAMMURABI = '50000000-0000-0000-0000-000000000005';

    private const REFORMATION = '50000000-0000-0000-0000-000000000006';

    private const COMPASS = '50000000-0000-0000-0000-000000000007';

    private const HERODOTUS = '50000000-0000-0000-0000-000000000008';

    // ── Relationship IDs (stable, seeder-specific) ───────────────────────────

    // Prefix b0 = relationship seeder IDs
    private const R01 = 'b0000000-0000-0000-0000-000000000001';

    private const R02 = 'b0000000-0000-0000-0000-000000000002';

    private const R03 = 'b0000000-0000-0000-0000-000000000003';

    private const R04 = 'b0000000-0000-0000-0000-000000000004';

    private const R05 = 'b0000000-0000-0000-0000-000000000005';

    private const R06 = 'b0000000-0000-0000-0000-000000000006';

    private const R07 = 'b0000000-0000-0000-0000-000000000007';

    private const R08 = 'b0000000-0000-0000-0000-000000000008';

    private const R09 = 'b0000000-0000-0000-0000-000000000009';

    private const R10 = 'b0000000-0000-0000-0000-000000000010';

    private const R11 = 'b0000000-0000-0000-0000-000000000011';

    private const R12 = 'b0000000-0000-0000-0000-000000000012';

    private const R13 = 'b0000000-0000-0000-0000-000000000013';

    private const R14 = 'b0000000-0000-0000-0000-000000000014';

    private const R15 = 'b0000000-0000-0000-0000-000000000015';

    private const R16 = 'b0000000-0000-0000-0000-000000000016';

    private const R17 = 'b0000000-0000-0000-0000-000000000017';

    private const R18 = 'b0000000-0000-0000-0000-000000000018';

    private const R19 = 'b0000000-0000-0000-0000-000000000019';

    private const R20 = 'b0000000-0000-0000-0000-000000000020';

    private const R21 = 'b0000000-0000-0000-0000-000000000021';

    private const R22 = 'b0000000-0000-0000-0000-000000000022';

    private const R23 = 'b0000000-0000-0000-0000-000000000023';

    private const R24 = 'b0000000-0000-0000-0000-000000000024';

    private const R25 = 'b0000000-0000-0000-0000-000000000025';

    private const R26 = 'b0000000-0000-0000-0000-000000000026';

    private const R27 = 'b0000000-0000-0000-0000-000000000027';

    private const R28 = 'b0000000-0000-0000-0000-000000000028';

    private const R29 = 'b0000000-0000-0000-0000-000000000029';

    private const R30 = 'b0000000-0000-0000-0000-000000000030';

    private const R31 = 'b0000000-0000-0000-0000-000000000031';

    private const R32 = 'b0000000-0000-0000-0000-000000000032';

    private const R33 = 'b0000000-0000-0000-0000-000000000033';

    private const R34 = 'b0000000-0000-0000-0000-000000000034';

    private const R35 = 'b0000000-0000-0000-0000-000000000035';

    private const R36 = 'b0000000-0000-0000-0000-000000000036';

    private const R37 = 'b0000000-0000-0000-0000-000000000037';

    private const R38 = 'b0000000-0000-0000-0000-000000000038';

    private const R39 = 'b0000000-0000-0000-0000-000000000039';

    private const R40 = 'b0000000-0000-0000-0000-000000000040';

    private const R41 = 'b0000000-0000-0000-0000-000000000041';

    private const R42 = 'b0000000-0000-0000-0000-000000000042';

    private const R43 = 'b0000000-0000-0000-0000-000000000043';

    private const R44 = 'b0000000-0000-0000-0000-000000000044';

    private const R45 = 'b0000000-0000-0000-0000-000000000045';

    private const R46 = 'b0000000-0000-0000-0000-000000000046';

    private const R47 = 'b0000000-0000-0000-0000-000000000047';

    private const R48 = 'b0000000-0000-0000-0000-000000000048';

    private const R49 = 'b0000000-0000-0000-0000-000000000049';

    private const R50 = 'b0000000-0000-0000-0000-000000000050';

    public function run(): void
    {
        $now = now();

        foreach ($this->buildRelationships() as $r) {
            DB::statement(
                <<<'SQL'
                    INSERT INTO relationships
                        (relationship_id, source_entity_id, target_entity_id,
                         relationship_type, temporal_start, temporal_end,
                         start_year, end_year,
                         description, confidence, source_citations,
                         created_by, created_at)
                    VALUES (?, ?, ?,
                            ?::relationship_type, ?, ?,
                            ?, ?,
                            ?, ?::confidence_level, ?::jsonb,
                            ?, ?)
                    ON CONFLICT (relationship_id) DO UPDATE SET
                        source_entity_id = EXCLUDED.source_entity_id,
                        target_entity_id = EXCLUDED.target_entity_id,
                        relationship_type = EXCLUDED.relationship_type,
                        temporal_start = EXCLUDED.temporal_start,
                        temporal_end = EXCLUDED.temporal_end,
                        start_year = EXCLUDED.start_year,
                        end_year = EXCLUDED.end_year,
                        description = EXCLUDED.description,
                        confidence = EXCLUDED.confidence,
                        source_citations = EXCLUDED.source_citations,
                        created_by = EXCLUDED.created_by,
                        created_at = EXCLUDED.created_at
                    SQL,
                [
                    $r['id'],
                    $r['source'],
                    $r['target'],
                    $r['type'],
                    $r['start'] ?? null,
                    $r['end'] ?? null,
                    self::extractYear($r['start'] ?? null),
                    self::extractYear($r['end'] ?? null),
                    $r['desc'] ?? null,
                    $r['confidence'] ?? 'medium',
                    isset($r['citations']) ? json_encode($r['citations']) : null,
                    'seeder',
                    $now,
                ],
            );
        }

        $exitCode = Artisan::call('entity:backfill');
        if ($exitCode !== 0) {
            throw new RuntimeException('Entity backfill failed after relationship seeding.');
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    //  Relationship definitions
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * @return list<array<string, mixed>>
     */
    private function buildRelationships(): array
    {
        return [
            // ══════════════════════════════════════════════════════════════════
            //  GENGHIS KHAN & THE MONGOL WORLD
            // ══════════════════════════════════════════════════════════════════

            // Genghis Khan → founded → Mongol Empire
            [
                'id' => self::R01,
                'source' => self::GENGHIS,
                'target' => self::MONGOL,
                'type' => 'founded',
                'start' => '1206',
                'end' => '1206',
                'desc' => 'Temüjin proclaimed Great Khan at a kurultai on the banks of the Onon River, formally establishing the Mongol Empire.',
                'confidence' => 'high',
                'citations' => [['source' => 'The Secret History of the Mongols', 'year' => 1240]],
            ],

            // Genghis Khan → rules → Mongol Empire
            [
                'id' => self::R02,
                'source' => self::GENGHIS,
                'target' => self::MONGOL,
                'type' => 'rules',
                'start' => '1206',
                'end' => '1227',
                'desc' => 'Ruled as first Great Khan (Khagan) until his death during the Xi Xia campaign.',
                'confidence' => 'high',
            ],

            // Genghis Khan → born_in → Mongol Empire territory (using Mongol as proxy)
            [
                'id' => self::R03,
                'source' => self::GENGHIS,
                'target' => self::MONGOL,
                'type' => 'born_in',
                'start' => '1162',
                'end' => '1162',
                'desc' => 'Born as Temüjin near Burkhan Khaldun in the Khentii Mountains of modern Mongolia.',
                'confidence' => 'medium',
                'citations' => [['source' => 'Ratchnevsky, Genghis Khan: His Life and Legacy', 'year' => 1991]],
            ],

            // Genghis Khan → died_in → Mongol Empire territory
            [
                'id' => self::R04,
                'source' => self::GENGHIS,
                'target' => self::MONGOL,
                'type' => 'died_in',
                'start' => '1227',
                'end' => '1227',
                'desc' => 'Died during the campaign against Western Xia; exact location and cause remain debated.',
                'confidence' => 'medium',
            ],

            // Genghis Khan → commanded → Praetorian Guard equivalent: his keshig
            // (using Silk Road as proxy for the trade network he protected)
            // Better: Genghis Khan → at_war_with → Byzantine (through intermediaries)
            // Actually let's use a more accurate relationship:

            // Mongol Empire → at_war_with → Byzantine Empire (indirect frontier conflicts)
            [
                'id' => self::R05,
                'source' => self::MONGOL,
                'target' => self::BYZANTINE,
                'type' => 'at_war_with',
                'start' => '1241',
                'end' => '1243',
                'desc' => 'Mongol incursions into Anatolia following the Battle of Köse Dağ (1243) against the Seljuk Sultanate of Rum, a Byzantine buffer state.',
                'confidence' => 'medium',
                'citations' => [['source' => 'Jackson, The Mongols and the West', 'year' => 2005]],
            ],

            // Mongol Empire → controlled Silk Road
            [
                'id' => self::R06,
                'source' => self::MONGOL,
                'target' => self::SILK_ROAD,
                'type' => 'controlled_by',
                'start' => '1206',
                'end' => '1368',
                'desc' => 'The Pax Mongolica secured overland trade routes, enabling unprecedented Silk Road commerce under Mongol protection.',
                'confidence' => 'high',
                'citations' => [['source' => 'Allsen, Culture and Conquest in Mongol Eurasia', 'year' => 2001]],
            ],

            // Genghis Khan → caused → Migration Period (stretching the link for demo — the Mongol invasions triggered massive population movements)
            [
                'id' => self::R07,
                'source' => self::MONGOL,
                'target' => self::PLAGUE,
                'type' => 'contributed_to',
                'start' => '1206',
                'end' => '1347',
                'desc' => 'Mongol trade networks and military campaigns may have facilitated the westward spread of Yersinia pestis from Central Asian reservoirs to the Black Sea.',
                'confidence' => 'low',
                'citations' => [['source' => 'Sussman, Was the Black Death in India and China?', 'year' => 2011]],
            ],

            // Mongol Empire → succeeded_by → Ottoman Empire (in terms of Eurasian dominance)
            [
                'id' => self::R08,
                'source' => self::MONGOL,
                'target' => self::OTTOMAN,
                'type' => 'weakened',
                'start' => '1243',
                'end' => '1335',
                'desc' => 'Mongol defeat of the Seljuk Sultanate of Rum at Köse Dağ weakened central Anatolian authority, creating the power vacuum that allowed the Ottoman beylik to rise.',
                'confidence' => 'medium',
                'citations' => [['source' => 'Kafadar, Between Two Worlds: The Construction of the Ottoman State', 'year' => 1995]],
            ],

            // ══════════════════════════════════════════════════════════════════
            //  ROMAN / BYZANTINE NETWORK
            // ══════════════════════════════════════════════════════════════════

            // Caesar → commanded → Praetorian Guard (anachronistic but close — he had a personal guard)
            [
                'id' => self::R09,
                'source' => self::CAESAR,
                'target' => self::ROMAN,
                'type' => 'rules',
                'start' => '-0049',
                'end' => '-0044',
                'desc' => 'Dictator perpetuo of the Roman Republic following civil war victory over Pompey.',
                'confidence' => 'high',
                'citations' => [['source' => 'Suetonius, The Twelve Caesars', 'year' => 121]],
            ],

            // Caesar → born_in → Roman Empire territory
            [
                'id' => self::R10,
                'source' => self::CAESAR,
                'target' => self::ROMAN,
                'type' => 'born_in',
                'start' => '-0100',
                'end' => '-0100',
                'desc' => 'Born in the Subura district of Rome to the patrician gens Julia.',
                'confidence' => 'high',
            ],

            // Caesar → died_in → Roman Empire territory
            [
                'id' => self::R11,
                'source' => self::CAESAR,
                'target' => self::ROMAN,
                'type' => 'died_in',
                'start' => '-0044',
                'end' => '-0044',
                'desc' => 'Assassinated in the Theatre of Pompey on the Ides of March by a conspiracy of senators led by Brutus and Cassius.',
                'confidence' => 'high',
                'citations' => [['source' => 'Plutarch, Life of Caesar', 'year' => 100]],
            ],

            // Caesar → assassinated_by (abstract — no "Brutus" entity, so link to Roman Republic)
            [
                'id' => self::R12,
                'source' => self::CAESAR,
                'target' => self::PRAETORIAN,
                'type' => 'commanded',
                'start' => '-0058',
                'end' => '-0050',
                'desc' => 'As proconsul of Gaul, Caesar commanded legions that would later become the core of his civil war army (precursors to the Praetorian concept).',
                'confidence' => 'medium',
            ],

            // Praetorian Guard → part_of → Roman Empire
            [
                'id' => self::R13,
                'source' => self::PRAETORIAN,
                'target' => self::ROMAN,
                'type' => 'part_of',
                'start' => '-0027',
                'end' => '0312',
                'desc' => 'Elite household troops of the Roman emperors, formally established by Augustus and disbanded by Constantine I.',
                'confidence' => 'high',
            ],

            // Byzantine → succeeded_by relationship with Roman Empire
            [
                'id' => self::R14,
                'source' => self::ROMAN,
                'target' => self::BYZANTINE,
                'type' => 'succeeded_by',
                'start' => '0395',
                'end' => '0476',
                'desc' => 'The eastern continuation of the Roman Empire after the permanent division of 395 CE; survived the fall of the Western Empire in 476.',
                'confidence' => 'high',
                'citations' => [['source' => 'Cameron, The Mediterranean World in Late Antiquity', 'year' => 2011]],
            ],

            // Constantinople → capital_of → Byzantine Empire
            [
                'id' => self::R15,
                'source' => self::CONSTANTINOPLE,
                'target' => self::BYZANTINE,
                'type' => 'capital_of',
                'start' => '0330',
                'end' => '1453',
                'desc' => 'Founded as Nova Roma by Constantine I in 330 CE; served as the imperial capital for over a millennium.',
                'confidence' => 'high',
            ],

            // Constantinople → capital_of → Ottoman Empire (after conquest)
            [
                'id' => self::R16,
                'source' => self::CONSTANTINOPLE,
                'target' => self::OTTOMAN,
                'type' => 'capital_of',
                'start' => '1453',
                'end' => '1922',
                'desc' => 'Renamed Istanbul and made the Ottoman capital after Mehmed II\'s conquest.',
                'confidence' => 'high',
            ],

            // Fall of Constantinople → resulted_from → Ottoman expansion
            [
                'id' => self::R17,
                'source' => self::FALL_CONST,
                'target' => self::OTTOMAN,
                'type' => 'resulted_from',
                'start' => '1453',
                'end' => '1453',
                'desc' => 'The 53-day siege by Sultan Mehmed II resulted in the fall of the last bastion of the Roman Empire.',
                'confidence' => 'high',
                'citations' => [['source' => 'Runciman, The Fall of Constantinople 1453', 'year' => 1965]],
            ],

            // Fall of Constantinople → weakened → Byzantine Empire
            [
                'id' => self::R18,
                'source' => self::FALL_CONST,
                'target' => self::BYZANTINE,
                'type' => 'destroyed_by',
                'start' => '1453',
                'end' => '1453',
                'desc' => 'The fall of Constantinople marked the final destruction of the Byzantine Empire.',
                'confidence' => 'high',
            ],

            // Fall of Constantinople → contributed_to → Renaissance
            [
                'id' => self::R19,
                'source' => self::FALL_CONST,
                'target' => self::RENAISSANCE,
                'type' => 'contributed_to',
                'start' => '1453',
                'end' => '1500',
                'desc' => 'Greek scholars fleeing Constantinople brought manuscripts and classical knowledge to Italy, accelerating the Renaissance.',
                'confidence' => 'medium',
                'citations' => [['source' => 'Wilson, From Byzantium to Italy', 'year' => 2017]],
            ],

            // Fall of Constantinople → located_at → Constantinople
            [
                'id' => self::R41,
                'source' => self::FALL_CONST,
                'target' => self::CONSTANTINOPLE,
                'type' => 'located_at',
                'start' => '1453',
                'end' => '1453',
                'desc' => 'The siege and capture occurred at Constantinople in 1453.',
                'confidence' => 'high',
            ],

            // Murad II → rules → Ottoman Empire
            [
                'id' => self::R42,
                'source' => self::MURAD_II,
                'target' => self::OTTOMAN,
                'type' => 'rules',
                'start' => '1421',
                'end' => '1451',
                'desc' => 'Murad II ruled the Ottoman Empire and restored political stability after internal and external crises.',
                'confidence' => 'high',
            ],

            // Mehmed II → rules → Ottoman Empire
            [
                'id' => self::R43,
                'source' => self::MEHMED_II,
                'target' => self::OTTOMAN,
                'type' => 'rules',
                'start' => '1451',
                'end' => '1481',
                'desc' => 'Mehmed II ruled as Ottoman sultan and expanded the empire after conquering Constantinople.',
                'confidence' => 'high',
            ],

            // Mehmed II → victorious_at → Fall of Constantinople
            [
                'id' => self::R44,
                'source' => self::MEHMED_II,
                'target' => self::FALL_CONST,
                'type' => 'victorious_at',
                'start' => '1453',
                'end' => '1453',
                'desc' => 'As Ottoman commander, Mehmed II won the siege that captured Constantinople.',
                'confidence' => 'high',
            ],

            // Constantine XI → rules → Byzantine Empire
            [
                'id' => self::R45,
                'source' => self::CONSTANTINE_XI,
                'target' => self::BYZANTINE,
                'type' => 'rules',
                'start' => '1449',
                'end' => '1453',
                'desc' => 'Constantine XI was the final reigning Byzantine emperor until the city fell in 1453.',
                'confidence' => 'high',
            ],

            // Constantine XI → died_in → Fall of Constantinople
            [
                'id' => self::R46,
                'source' => self::CONSTANTINE_XI,
                'target' => self::FALL_CONST,
                'type' => 'died_in',
                'start' => '1453',
                'end' => '1453',
                'desc' => 'Constantine XI was killed during the final defense of Constantinople.',
                'confidence' => 'high',
            ],

            // Edirne → capital_of → Ottoman Empire (pre-1453)
            [
                'id' => self::R47,
                'source' => self::EDIRNE,
                'target' => self::OTTOMAN,
                'type' => 'capital_of',
                'start' => '1369',
                'end' => '1453',
                'desc' => 'Edirne (Adrianople) served as the principal Ottoman capital before Constantinople.',
                'confidence' => 'high',
            ],

            // Murad II → victorious_at → Battle of Varna
            [
                'id' => self::R48,
                'source' => self::MURAD_II,
                'target' => self::VARNA,
                'type' => 'victorious_at',
                'start' => '1444',
                'end' => '1444',
                'desc' => 'Murad II led the Ottoman victory over crusader forces at Varna.',
                'confidence' => 'high',
            ],

            // Ottoman Empire → victorious_at → Battle of Varna
            [
                'id' => self::R49,
                'source' => self::OTTOMAN,
                'target' => self::VARNA,
                'type' => 'victorious_at',
                'start' => '1444',
                'end' => '1444',
                'desc' => 'The Ottoman victory at Varna secured strategic dominance in the Balkans.',
                'confidence' => 'high',
            ],

            // Battle of Varna → enabled → Fall of Constantinople
            [
                'id' => self::R50,
                'source' => self::VARNA,
                'target' => self::FALL_CONST,
                'type' => 'enabled',
                'start' => '1444',
                'end' => '1453',
                'desc' => 'The defeat of crusader intervention at Varna enabled later Ottoman concentration on Constantinople.',
                'confidence' => 'medium',
            ],

            // Migration Period → weakened → Roman Empire
            [
                'id' => self::R20,
                'source' => self::MIGRATION,
                'target' => self::ROMAN,
                'type' => 'weakened',
                'start' => '0375',
                'end' => '0476',
                'desc' => 'Successive waves of Germanic, Hunnic, and Slavic migrations progressively dismembered the Western Roman Empire.',
                'confidence' => 'high',
            ],

            // ══════════════════════════════════════════════════════════════════
            //  EVENTS & CAUSAL WEB
            // ══════════════════════════════════════════════════════════════════

            // Black Death → weakened → Byzantine Empire
            [
                'id' => self::R21,
                'source' => self::PLAGUE,
                'target' => self::BYZANTINE,
                'type' => 'weakened',
                'start' => '1347',
                'end' => '1353',
                'desc' => 'The Black Death devastated Constantinople and the remaining Byzantine territories, reducing the empire\'s already declining population and military capacity.',
                'confidence' => 'high',
            ],

            // Black Death → weakened → Ottoman Empire (also affected)
            [
                'id' => self::R22,
                'source' => self::PLAGUE,
                'target' => self::OTTOMAN,
                'type' => 'weakened',
                'start' => '1347',
                'end' => '1353',
                'desc' => 'Ottoman territories in Anatolia and the Balkans suffered significant mortality, temporarily slowing expansion.',
                'confidence' => 'medium',
            ],

            // Gutenberg → enabled → Reformation
            [
                'id' => self::R23,
                'source' => self::GUTENBERG,
                'target' => self::REFORMATION,
                'type' => 'enabled',
                'start' => '1450',
                'end' => '1517',
                'desc' => 'The printing press enabled rapid dissemination of Luther\'s 95 Theses and Protestant pamphlets, making the Reformation a mass movement.',
                'confidence' => 'high',
                'citations' => [['source' => 'Eisenstein, The Printing Press as an Agent of Change', 'year' => 1979]],
            ],

            // Gutenberg → contributed_to → Renaissance
            [
                'id' => self::R24,
                'source' => self::GUTENBERG,
                'target' => self::RENAISSANCE,
                'type' => 'contributed_to',
                'start' => '1450',
                'end' => '1500',
                'desc' => 'Movable type printing dramatically increased access to classical texts, fueling humanist scholarship across Europe.',
                'confidence' => 'high',
            ],

            // Hundred Years' War → resulted_from → succession dispute (link to Magna Carta as precedent for limiting royal power)
            [
                'id' => self::R25,
                'source' => self::MAGNA_CARTA,
                'target' => self::HUNDRED_YRS,
                'type' => 'contributed_to',
                'start' => '1215',
                'end' => '1337',
                'desc' => 'Magna Carta established principles of baronial consent and legal constraint on the crown; the constitutional tensions it created fed into the feudal disputes underlying the Hundred Years\' War.',
                'confidence' => 'low',
            ],

            // Peace of Westphalia → resulted_from → Reformation
            [
                'id' => self::R26,
                'source' => self::WESTPHALIA,
                'target' => self::REFORMATION,
                'type' => 'resulted_from',
                'start' => '1618',
                'end' => '1648',
                'desc' => 'The Thirty Years\' War — concluded by the Peace of Westphalia — was fundamentally driven by the religious divisions created by the Reformation.',
                'confidence' => 'high',
                'citations' => [['source' => 'Wilson, The Thirty Years War', 'year' => 2009]],
            ],

            // ══════════════════════════════════════════════════════════════════
            //  ECONOMY & TRADE
            // ══════════════════════════════════════════════════════════════════

            // Silk Road → passes_through → Constantinople
            [
                'id' => self::R27,
                'source' => self::SILK_ROAD,
                'target' => self::CONSTANTINOPLE,
                'type' => 'passes_through',
                'start' => '0330',
                'end' => '1453',
                'desc' => 'Constantinople served as the western terminus of the overland Silk Road, controlling the gateway between Asia and Europe.',
                'confidence' => 'high',
            ],

            // Roman Denarius → minted_by → Roman Empire
            [
                'id' => self::R28,
                'source' => self::DENARIUS,
                'target' => self::ROMAN,
                'type' => 'minted_by',
                'start' => '-0211',
                'end' => '0305',
                'desc' => 'Standard silver coin of the Roman Republic and Empire, minted at Rome and provincial mints.',
                'confidence' => 'high',
            ],

            // Laurion mines → supplies → Roman Empire (and earlier Athens)
            [
                'id' => self::R29,
                'source' => self::LAURION,
                'target' => self::ROMAN,
                'type' => 'supplies',
                'start' => '-0200',
                'end' => '0100',
                'desc' => 'The silver mines of Laurion continued limited production under Roman control after the conquest of Greece.',
                'confidence' => 'medium',
            ],

            // Indian Ocean Trade → connects → Alexandria
            [
                'id' => self::R30,
                'source' => self::INDIAN_OCEAN,
                'target' => self::ALEXANDRIA,
                'type' => 'connects',
                'start' => '-0300',
                'end' => '1500',
                'desc' => 'Alexandria\'s Red Sea port of Berenice linked Egypt to the Indian Ocean monsoon trade network.',
                'confidence' => 'high',
                'citations' => [['source' => 'Casson, The Periplus Maris Erythraei', 'year' => 1989]],
            ],

            // Cornish Tin → trades_with → Roman Empire
            [
                'id' => self::R31,
                'source' => self::CORNISH_TIN,
                'target' => self::ROMAN,
                'type' => 'trades_with',
                'start' => '-0043',
                'end' => '0410',
                'desc' => 'After the Roman invasion of Britain, Cornish tin was extracted under imperial administration and traded across the empire.',
                'confidence' => 'medium',
            ],

            // ══════════════════════════════════════════════════════════════════
            //  CULTURE & KNOWLEDGE
            // ══════════════════════════════════════════════════════════════════

            // Herodotus → influenced_by relationship: Iliad influenced Herodotus
            [
                'id' => self::R32,
                'source' => self::HERODOTUS,
                'target' => self::ILIAD,
                'type' => 'influenced_by',
                'start' => '-0450',
                'end' => '-0420',
                'desc' => 'Herodotus frames the Histories as an investigation of the conflict between Greece and Asia, directly echoing the Trojan War narrative of the Iliad.',
                'confidence' => 'medium',
                'citations' => [['source' => 'Lateiner, The Historical Method of Herodotus', 'year' => 1989]],
            ],

            // Code of Hammurabi → located_at → Laurion (actually Susa, but closest PLACE entity is Alexandria)
            // Better: Hammurabi influenced Magna Carta (legal tradition)
            [
                'id' => self::R33,
                'source' => self::HAMMURABI,
                'target' => self::MAGNA_CARTA,
                'type' => 'inspired',
                'start' => '-1750',
                'end' => '1215',
                'desc' => 'While not a direct source, the Code of Hammurabi represents the earliest known codified law tradition; Magna Carta\'s emphasis on written legal constraints follows in this deep lineage.',
                'confidence' => 'low',
            ],

            // Angkor Wat → built_by relationship → (no Khmer entity, link to Indian Ocean influence)
            [
                'id' => self::R34,
                'source' => self::ANGKOR,
                'target' => self::INDIAN_OCEAN,
                'type' => 'influenced_by',
                'start' => '0802',
                'end' => '1431',
                'desc' => 'The Khmer Empire that built Angkor was deeply connected to Indian Ocean trade networks, importing Hindu and Buddhist cultural forms via maritime contacts.',
                'confidence' => 'medium',
            ],

            // Compass → enabled → Indian Ocean Trade expansion
            [
                'id' => self::R35,
                'source' => self::COMPASS,
                'target' => self::INDIAN_OCEAN,
                'type' => 'enabled',
                'start' => '1100',
                'end' => '1500',
                'desc' => 'The magnetic compass, transmitted from China to the Arab world, dramatically improved navigation in the Indian Ocean, enabling longer open-sea voyages.',
                'confidence' => 'high',
            ],

            // Quran → official_religion_of → Ottoman Empire
            [
                'id' => self::R36,
                'source' => self::QURAN,
                'target' => self::OTTOMAN,
                'type' => 'official_religion_of',
                'start' => '1299',
                'end' => '1922',
                'desc' => 'Islam as codified in the Quran was the official religion of the Ottoman state; the Sultan also held the title of Caliph from 1517.',
                'confidence' => 'high',
            ],

            // Linear B → adopted → (by Ptolemaic bureaucracy is a stretch — link to Alexandria as knowledge centre)
            [
                'id' => self::R37,
                'source' => self::LINEAR_B,
                'target' => self::ALEXANDRIA,
                'type' => 'located_at',
                'start' => '-1400',
                'end' => '-1200',
                'desc' => 'Linear B tablets, the earliest Greek writing system, document Mycenaean palace economies; knowledge of them was lost until decipherment in 1952.',
                'confidence' => 'medium',
            ],

            // Renaissance → influenced_by → Ptolemaic Dynasty (Hellenistic learning preserved)
            [
                'id' => self::R38,
                'source' => self::RENAISSANCE,
                'target' => self::PTOLEMY,
                'type' => 'influenced_by',
                'start' => '1300',
                'end' => '1600',
                'desc' => 'Ptolemaic Alexandria\'s Library and Museum preserved Greek philosophical and scientific works that became foundational texts for Renaissance humanists.',
                'confidence' => 'medium',
            ],

            // Great Wall → built_by relationship (no specific Chinese dynasty entity — link defensively)
            [
                'id' => self::R39,
                'source' => self::GREAT_WALL,
                'target' => self::MONGOL,
                'type' => 'prevented',
                'start' => '-0221',
                'end' => '1644',
                'desc' => 'The Great Wall was built and repeatedly extended to defend against steppe nomads, including the Mongols — though Genghis Khan famously breached it.',
                'confidence' => 'medium',
            ],

            // Bologna university → taught_at (knowledge link)
            [
                'id' => self::R40,
                'source' => self::BOLOGNA,
                'target' => self::RENAISSANCE,
                'type' => 'contributed_to',
                'start' => '1088',
                'end' => '1600',
                'desc' => 'As the oldest continuously operating university, Bologna trained generations of jurists and humanists who helped shape Renaissance thought.',
                'confidence' => 'high',
                'citations' => [['source' => 'Rashdall, The Universities of Europe in the Middle Ages', 'year' => 1895]],
            ],
        ];
    }

    private static function extractYear(?string $temporal): ?int
    {
        if ($temporal === null || trim($temporal) === '') {
            return null;
        }

        if (! preg_match('/^-?\d+/', $temporal, $matches)) {
            return null;
        }

        return (int) $matches[0];
    }
}
