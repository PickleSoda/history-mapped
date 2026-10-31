<?php

declare(strict_types=1);

namespace Tests\Feature\MapStory;

use Illuminate\Support\Facades\File;

/** A small valid schema-1 map story, and a scratch directory to sync it from. */
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
