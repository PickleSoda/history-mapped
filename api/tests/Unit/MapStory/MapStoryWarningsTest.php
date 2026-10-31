<?php

declare(strict_types=1);

namespace Tests\Unit\MapStory;

use App\Support\MapStory\MapStoryWarnings;
use PHPUnit\Framework\TestCase;

class MapStoryWarningsTest extends TestCase
{
    /** @return array<string, mixed> a valid small battle with no warnings but its text lengths */
    private function doc(): array
    {
        $narrative = str_repeat('The armies close on each other across the plain. ', 4);

        return [
            'schema' => 3, 'slug' => 'battle-of-x', 'kind' => 'battle', 'title' => 'Battle of X', 'date_label' => '1 May 100 BC',
            'year' => -100, 'intro' => str_repeat('Background of the battle. ', 12), 'outcome' => 'The red side wins the day.',
            'sides' => [['id' => 'red', 'name' => 'Red', 'color' => '#b91c1c'], ['id' => 'blue', 'name' => 'Blue', 'color' => '#1d4ed8']],
            'units' => [
                ['id' => 'foot', 'side' => 'red', 'kind' => 'infantry', 'label' => 'Foot'],
                ['id' => 'ships', 'side' => 'blue', 'kind' => 'warship', 'label' => 'Ships'],
            ],
            'features' => [['id' => 'bay', 'kind' => 'sea', 'label' => 'Bay', 'area' => [[16.0, 41.0], [16.1, 41.0], [16.1, 41.1], [16.0, 41.1]]]],
            'steps' => array_map(fn (int $i) => [
                'id' => "s{$i}", 'title' => "Step {$i}", 'narrative' => $narrative,
                'positions' => $i === 1 ? ['foot' => ['at' => [16.2, 41.05]], 'ships' => ['at' => [16.05, 41.05]]] : [],
            ], range(1, 5)),
        ];
    }

    public function test_a_plausible_story_has_no_warnings(): void
    {
        $this->assertSame([], MapStoryWarnings::of($this->doc()));
    }

    public function test_the_committed_stories_have_none(): void
    {
        foreach (glob(dirname(__DIR__, 3).'/resources/map-stories/*.json') as $path) {
            $this->assertSame([], MapStoryWarnings::of(json_decode((string) file_get_contents($path), true)), basename($path));
        }
    }

    public function test_a_unit_that_jumps_without_an_arrow(): void
    {
        $doc = $this->doc();
        $doc['steps'][1]['positions']['foot'] = ['at' => [16.25, 41.05]];

        $this->assertSame(["step 's2': foot moves 4193 m with no move arrow"], MapStoryWarnings::of($doc));

        $doc['steps'][1]['moves'] = [['unit' => 'foot', 'type' => 'advance', 'path' => [[16.2, 41.05], [16.25, 41.05]]]];
        $this->assertSame([], MapStoryWarnings::of($doc));
    }

    public function test_teleport_distance_scales_with_the_kind(): void
    {
        $doc = $this->doc();
        $doc['kind'] = 'campaign';
        $doc['steps'][1]['positions']['foot'] = ['at' => [16.25, 41.05]];

        $this->assertSame([], array_values(array_filter(MapStoryWarnings::of($doc), fn ($w) => str_contains($w, 'no move arrow'))));
    }

    public function test_a_point_far_from_the_rest(): void
    {
        $doc = $this->doc();
        $doc['steps'][2]['notes'] = [['at' => [18.0, 41.05], 'text' => 'Far away']];

        $this->assertStringContainsString('1 point(s) lie more than 20 km', implode(' ', MapStoryWarnings::of($doc)));
    }

    public function test_a_unit_acted_on_before_it_is_placed(): void
    {
        $doc = $this->doc();
        $doc['units'][] = ['id' => 'horse', 'side' => 'red', 'kind' => 'cavalry', 'label' => 'Horse'];
        $doc['steps'][1]['moves'] = [['unit' => 'horse', 'type' => 'charge', 'path' => [[16.2, 41.0], [16.2, 41.01]]]];
        $doc['steps'][1]['focus'] = ['horse'];

        $warnings = MapStoryWarnings::of($doc);
        $this->assertContains("step 's2': horse has an arrow before it is placed (give it a position first)", $warnings);
        $this->assertContains("step 's2': focus on horse before it is placed", $warnings);
        $this->assertContains('units never placed: horse', $warnings);
    }

    public function test_ships_on_land_and_troops_at_sea(): void
    {
        $doc = $this->doc();
        $doc['steps'][0]['positions'] = ['foot' => ['at' => [16.05, 41.06]], 'ships' => ['at' => [16.2, 41.06]]];

        $warnings = MapStoryWarnings::of($doc);
        $this->assertContains("step 's1': foot (infantry) stands in the sea or a lake", $warnings);
        $this->assertContains("step 's1': ships (warship) is not on water — outside every sea/lake and over 400 m from a river or coast", $warnings);
    }

    public function test_text_lengths(): void
    {
        $doc = $this->doc();
        $doc['steps'][0]['narrative'] = 'Too short.';

        $this->assertSame(["step 's1'.narrative: only 10 characters (aim for 150–1100)"], MapStoryWarnings::of($doc));
    }
}
