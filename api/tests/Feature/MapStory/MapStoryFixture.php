<?php

declare(strict_types=1);

namespace Tests\Feature\MapStory;

use Illuminate\Support\Facades\File;

/** A small valid map story (schema 1, or 2 with every feature), and a scratch directory to sync it from. */
final class MapStoryFixture
{
    /** @return array<string, mixed> */
    public static function document(string $slug = 'battle-of-testfield', ?string $wikidata = 'Q179591'): array
    {
        return [
            'schema' => 1,
            'slug' => $slug,
            'kind' => 'battle',
            'entity' => array_filter(['name' => 'Battle of Testfield', 'wikidata' => $wikidata]),
            'title' => 'Battle of Testfield',
            'date_label' => '2 August 216 BC',
            'year' => -216,
            'intro' => 'Two armies meet beside a river.',
            'outcome' => 'The red army wins.',
            'sources' => [['title' => 'A source', 'kind' => 'web', 'url' => 'https://example.org']],
            'sides' => [
                [
                    'id' => 'red', 'name' => 'Red army', 'color' => '#b91c1c',
                    'polity' => ['name' => 'Carthage', 'wikidata' => 'Q6343'],
                    'commanders' => [['name' => 'Hannibal', 'wikidata' => 'Q8456'], ['name' => 'Nobody', 'wikidata' => 'Q999999999']],
                ],
                ['id' => 'blue', 'name' => 'Blue army', 'color' => '#1d4ed8', 'commanders' => [['name' => 'Varro']]],
            ],
            'units' => [
                ['id' => 'red-foot', 'side' => 'red', 'kind' => 'infantry', 'label' => 'Red foot'],
                ['id' => 'blue-horse', 'side' => 'blue', 'kind' => 'cavalry', 'label' => 'Blue horse'],
                ['id' => 'hannibal', 'side' => 'red', 'kind' => 'commander', 'label' => 'Hannibal', 'wikidata' => 'Q8456'],
            ],
            'terrain' => [
                ['id' => 'river', 'kind' => 'river', 'label' => 'River', 'line' => [[16.10, 41.30], [16.15, 41.31]]],
                ['id' => 'town', 'kind' => 'town', 'label' => 'Town', 'at' => [16.13, 41.30]],
            ],
            'steps' => [
                [
                    'id' => 'deploy', 'title' => 'Deployment', 'narrative' => 'The armies deploy.',
                    'positions' => [
                        'red-foot' => ['at' => [16.13, 41.30], 'facing' => 0, 'width' => 1200, 'depth' => 60, 'shape' => 'crescent'],
                        'blue-horse' => ['at' => [16.13, 41.31], 'facing' => 180, 'width' => 600],
                        'hannibal' => ['with' => 'red-foot'],
                    ],
                ],
                [
                    'id' => 'clash', 'title' => 'The clash', 'narrative' => 'They fight.',
                    'positions' => (object) [],
                    'moves' => [['unit' => 'blue-horse', 'type' => 'charge', 'path' => [[16.13, 41.31], [16.13, 41.305]]]],
                    'notes' => [['at' => [16.13, 41.303], 'text' => 'Clash', 'kind' => 'clash']],
                ],
            ],
        ];
    }

    /**
     * The same story as schema 2, using one of each schema-2 feature.
     *
     * @return array<string, mixed>
     */
    public static function v2Document(string $slug = 'battle-of-testfield'): array
    {
        $doc = self::document($slug);
        $doc['schema'] = 2;
        $doc['alt_sites'] = [['at' => [16.14, 41.31], 'label' => 'North bank', 'note' => 'An older theory']];
        $doc['sides'][0]['contingents'] = [['id' => 'gauls', 'name' => 'Gauls', 'color' => '#ea580c'], ['id' => 'spaniards', 'name' => 'Spaniards']];
        $doc['units'][0] += ['contingent' => 'gauls', 'strength_n' => 20000, 'ranks' => [['kind' => 'archers', 'share' => 0.3], ['kind' => 'heavy_infantry', 'share' => 0.7]]];
        $doc['units'][] = ['id' => 'standard', 'side' => 'red', 'kind' => 'standard', 'label' => 'Standard'];
        $doc['units'][] = ['id' => 'red-wing', 'side' => 'red', 'kind' => 'infantry', 'label' => 'Red wing', 'contingent' => 'spaniards'];
        $doc['terrain'][1]['conjectural'] = true;
        $doc['terrain'][] = ['id' => 'fill', 'kind' => 'mask', 'area' => [[16.10, 41.29], [16.11, 41.29], [16.11, 41.295]]];
        $doc['steps'][0] += [
            'light' => 'dawn', 'wind' => ['from' => 135, 'strength' => 'strong', 'label' => 'Volturnus'], 'sun' => ['from' => 90],
            'terrain_state' => ['town' => ['held_by' => 'red', 'state' => 'held']],
        ];
        $doc['steps'][0]['positions']['red-foot'] += ['lines' => 3, 'lanes' => 2, 'subunits' => 10, 'strength_n' => 18000];
        $doc['steps'][0]['positions']['blue-horse'] += ['frame' => false, 'conjectural' => true];
        $doc['steps'][0]['positions']['standard'] = ['with' => 'red-foot'];
        $doc['steps'][1]['positions'] = [
            'red-wing' => ['from' => 'red-foot', 'at' => [16.135, 41.30], 'width' => 300],
            'standard' => ['at' => [16.13, 41.301], 'state' => 'captured', 'by' => 'blue'],
        ];
        $doc['steps'][1]['terrain_state'] = ['town' => ['held_by' => null, 'state' => 'burning']];
        $doc['steps'][1]['moves'][0] += ['continues' => ['toward' => [16.2, 41.4], 'label' => 'to Rome'], 'orient' => 'path', 'conjectural' => true];
        $doc['steps'][1]['moves'][] = ['unit' => 'red-foot', 'type' => 'fire', 'path' => [[16.13, 41.30], [16.13, 41.31]], 'target' => 'blue-horse', 'arc' => true];
        $doc['steps'][1]['notes'][0]['conjectural'] = true;
        $doc['steps'][1]['beats'] = [
            ['label' => 'The wing rejoins the line', 'positions' => ['red-wing' => ['into' => 'red-foot']]],
            ['label' => 'The horse ram home', 'moves' => [['unit' => 'blue-horse', 'type' => 'ram', 'path' => [[16.13, 41.305], [16.13, 41.303]]]]],
        ];

        return $doc;
    }

    /**
     * A schema-3 epidemic: no sides, dated steps, step entities, generic
     * features (an outbreak, a route, a spread region, an area from an
     * entity, and a plain town), ambient on.
     *
     * @return array<string, mixed>
     */
    public static function v3Document(string $slug = 'plague-of-testland'): array
    {
        return [
            'schema' => 3,
            'slug' => $slug,
            'kind' => 'epidemic',
            'entity' => ['name' => 'Plague of Testland', 'wikidata' => 'Q42005'],
            'title' => 'The plague of Testland',
            'date_label' => '1346–1350',
            'year' => 1346,
            'ambient' => true,
            'intro' => 'A plague spreads along the trade routes.',
            'outcome' => 'A third of the people die.',
            'sources' => [['title' => 'A source']],
            'legend' => [['swatch' => '#7f1d1d', 'label' => 'Plague reached', 'style' => 'fill']],
            'sides' => [],
            'units' => [['id' => 'galleys', 'kind' => 'merchant_ship', 'label' => 'Galleys']],
            'features' => [
                ['id' => 'caffa', 'kind' => 'outbreak', 'label' => 'Caffa', 'at' => [35.38, 45.03], 'entity' => ['name' => 'Feodosia', 'wikidata' => 'Q130231']],
                [
                    'id' => 'sea-lane', 'kind' => 'route', 'route_kind' => 'trade', 'label' => 'Sea lane', 'goods' => ['grain'], 'active' => false,
                    'line' => [[35.38, 45.03], [35.0, 44.65], [34.62, 44.27], [28.97, 41.01], [15.55, 38.19]],
                ],
                ['id' => 'plague', 'kind' => 'region', 'region_kind' => 'spread', 'label' => 'Plague', 'area' => [[34.0, 44.0], [37.0, 44.0], [37.0, 46.0], [34.0, 46.0]]],
                ['id' => 'horde', 'kind' => 'region', 'region_kind' => 'extent', 'label' => 'The Horde', 'area' => [[40.0, 45.0], [41.0, 45.0], [41.0, 46.0]]],
                ['id' => 'town', 'kind' => 'town', 'label' => 'Town', 'at' => [30.0, 40.0]],
            ],
            'steps' => [
                [
                    'id' => 's1', 'title' => 'Siege of Caffa', 'narrative' => 'The besiegers fall ill.',
                    'date' => ['year' => 1346],
                    'entities' => [
                        ['name' => 'Jani Beg', 'wikidata' => 'Q313451', 'role' => 'besieger', 'show' => true],
                        ['name' => 'A later namesake', 'wikidata' => 'Q99'],
                    ],
                    'features' => [
                        'caffa' => ['state' => 'infected', 'value_n' => 1000, 'value_label' => '1,000 dead'],
                        'horde' => ['area_from_entity' => ['wikidata' => 'Q79965']],
                    ],
                    'positions' => ['galleys' => ['at' => [35.38, 45.03]]],
                ],
                [
                    'id' => 's2', 'title' => 'The galleys sail', 'narrative' => 'The plague goes west by sea.',
                    'date' => ['year' => 1347, 'month' => 10, 'end' => ['year' => 1348, 'month' => 3]],
                    'features' => [
                        'sea-lane' => ['active' => true, 'value_n' => 12],
                        'plague' => ['area' => [[[34.0, 44.0], [37.0, 44.0], [37.0, 46.0]], [[15.0, 37.0], [16.0, 37.0], [16.0, 39.0]]], 'intensity' => 0.8],
                    ],
                    'moves' => [['unit' => 'galleys', 'type' => 'spread', 'path' => [[35.38, 45.03], [15.55, 38.19]]]],
                ],
                [
                    'id' => 's3', 'title' => 'The plague abates', 'narrative' => 'Trade stops.',
                    'date' => ['year' => 1350],
                    'features' => ['sea-lane' => ['state' => 'disrupted'], 'caffa' => ['state' => 'recovered']],
                ],
            ],
        ];
    }

    /**
     * A chronicle's map layer: no entity, steps keyed to entries by sequence_order.
     *
     * @return array<string, mixed>
     */
    public static function chronicleLayer(string $slug = 'testland-trade-map', string $chronicle = 'testland-trade', array $entries = [0, 2]): array
    {
        $doc = self::v3Document($slug);
        unset($doc['entity'], $doc['ambient']);
        $doc['kind'] = 'trade_route';
        $doc['chronicle'] = ['slug' => $chronicle];
        $doc['steps'] = array_slice($doc['steps'], 0, count($entries));
        foreach ($entries as $i => $entry) {
            $doc['steps'][$i]['entry'] = $entry;
        }

        return $doc;
    }

    /** A fresh directory under storage/framework/testing; removed by the caller. */
    public static function directory(): string
    {
        $dir = storage_path('framework/testing/map-stories-'.bin2hex(random_bytes(4)));
        File::ensureDirectoryExists($dir);

        return $dir;
    }

    /** @param  array<string, mixed>  $doc */
    public static function write(string $dir, array $doc, ?string $file = null): string
    {
        $path = $dir.'/'.($file ?? $doc['slug'].'.json');
        file_put_contents($path, json_encode($doc, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

        return $path;
    }
}
