<?php

declare(strict_types=1);

namespace Tests\Feature\MapStory;

use App\Support\MapStory\MapStoryDocument;
use Tests\TestCase;

class MapStoryDocumentTest extends TestCase
{
    public function test_a_valid_document_has_no_errors(): void
    {
        $doc = json_decode(json_encode(MapStoryFixture::document()), true);

        $this->assertSame([], MapStoryDocument::errors($doc));
    }

    public function test_reports_broken_references_vocabulary_and_coordinates(): void
    {
        $doc = json_decode(json_encode(MapStoryFixture::document()), true);
        $doc['schema'] = 2;
        $doc['units'][0]['kind'] = 'dragons';
        $doc['sides'][1]['color'] = 'blue';
        $doc['terrain'][0]['line'] = [[16.1, 41.3]];
        $doc['steps'][0]['positions']['ghost'] = ['at' => [0, 0]];
        $doc['steps'][0]['positions']['blue-horse']['at'] = [200, 41.3];
        $doc['steps'][1]['moves'][0]['unit'] = 'nobody';
        $doc['steps'][1]['moves'][0]['type'] = 'teleport';

        $errors = implode("\n", MapStoryDocument::errors($doc));

        foreach ([
            'schema: must be 1',
            "units[0] (red-foot).kind: 'dragons'",
            'sides[1].color: #rrggbb',
            'a river needs `line` with ≥2 points',
            "step 'deploy'.positions.ghost: unknown unit",
            "step 'deploy'.positions.blue-horse.at: [lon, lat]",
            "step 'clash'.moves[0].unit: unknown unit 'nobody'",
            "step 'clash'.moves[0].type: one of",
        ] as $expected) {
            $this->assertStringContainsString($expected, $errors);
        }
    }

    public function test_a_first_placement_needs_a_point_or_an_escort(): void
    {
        $doc = json_decode(json_encode(MapStoryFixture::document()), true);
        unset($doc['steps'][0]['positions']['hannibal']['with']);
        $doc['steps'][0]['positions']['hannibal']['facing'] = 90;

        $this->assertContains("step 'deploy'.positions.hannibal: first placement needs `at` or `with`", MapStoryDocument::errors($doc));
    }

    public function test_rejects_a_non_object(): void
    {
        $this->assertSame(['document must be an object'], MapStoryDocument::errors([1, 2]));
        $this->assertSame(['document must be an object'], MapStoryDocument::errors('nope'));
    }
}
