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
        $doc['schema'] = 4;
        $doc['units'][0]['kind'] = 'dragons';
        $doc['sides'][1]['color'] = 'blue';
        $doc['terrain'][0]['line'] = [[16.1, 41.3]];
        $doc['steps'][0]['positions']['ghost'] = ['at' => [0, 0]];
        $doc['steps'][0]['positions']['blue-horse']['at'] = [200, 41.3];
        $doc['steps'][1]['moves'][0]['unit'] = 'nobody';
        $doc['steps'][1]['moves'][0]['type'] = 'teleport';

        $errors = implode("\n", MapStoryDocument::errors($doc));

        foreach ([
            'schema: must be 1, 2 or 3',
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

    public function test_a_valid_schema_2_document_has_no_errors(): void
    {
        $this->assertSame([], MapStoryDocument::errors($this->v2()));
    }

    public function test_a_schema_1_document_using_schema_2_fields_is_told_to_bump_the_schema(): void
    {
        $doc = $this->v2();
        $doc['schema'] = 1;

        $errors = implode("\n", MapStoryDocument::errors($doc));

        foreach ([
            'document: alt_sites need schema 2 — set `schema: 2`',
            'sides[0]: contingents need schema 2',
            'units[0] (red-foot): ranks, strength_n, contingent need schema 2',
            "units[3] (standard).kind: 'standard' needs schema 2",
            'terrain[1] (town): conjectural need schema 2',
            "terrain[2] (fill).kind: 'mask' needs schema 2",
            "step 'deploy': terrain_state, light, wind, sun need schema 2",
            "step 'deploy'.positions.red-foot: lines, lanes, subunits, strength_n need schema 2",
            "step 'clash'.positions.standard.state: 'captured' needs schema 2",
            "step 'clash'.moves[0]: continues, orient, conjectural need schema 2",
            "step 'clash'.beats[1].moves[0].type: 'ram' needs schema 2",
        ] as $expected) {
            $this->assertStringContainsString($expected, $errors);
        }
    }

    public function test_checks_beats_terrain_state_contingents_and_new_fields(): void
    {
        $doc = $this->v2();
        $doc['units'][4]['contingent'] = 'romans';
        $doc['sides'][0]['contingents'][1]['wikidata'] = '8680';
        $doc['units'][0]['ranks'][0]['share'] = 1.5;
        $doc['steps'][0]['positions']['red-foot']['lines'] = 6;
        $doc['steps'][0]['light'] = 'noon';
        $doc['steps'][0]['wind'] = ['strength' => 'gale'];
        $doc['steps'][0]['terrain_state'] = ['castle' => ['held_by' => 'red'], 'town' => ['held_by' => 'green', 'state' => 'ablaze']];
        unset($doc['steps'][1]['positions']['standard']['by']);
        $doc['steps'][1]['moves'][1]['target'] = 'nobody';
        $doc['steps'][1]['moves'][0]['continues'] = ['label' => 'away'];
        $doc['steps'][1]['beats'][0]['label'] = '';
        $doc['steps'][1]['beats'][] = ['label' => 'Nothing happens'];
        $doc['steps'][0]['beats'] = array_fill(0, 5, ['label' => 'b', 'moves' => [['unit' => 'red-foot', 'type' => 'advance', 'path' => [[16.13, 41.30], [16.13, 41.30]]]]]);
        $doc['alt_sites'][] = ['at' => [16.1, 41.3]];

        $errors = implode("\n", MapStoryDocument::errors($doc));

        foreach ([
            "units[4] (red-wing).contingent: 'romans' is not a contingent of side 'red'",
            'sides[0].contingents[1].wikidata: a Q-id like Q8680',
            'units[0] (red-foot).ranks[0]: {kind: a unit kind, share: 0–1}',
            "step 'deploy'.positions.red-foot.lines: a whole number 1–5",
            "step 'deploy'.light: one of night, dawn, day, dusk",
            "step 'deploy'.wind: {from: degrees, strength?, label?}",
            "step 'deploy'.terrain_state.castle: unknown terrain",
            "step 'deploy'.terrain_state.town.held_by: unknown side 'green'",
            "step 'deploy'.terrain_state.town.state: one of held, contested",
            "step 'deploy'.beats: 5 beats (at most 4)",
            "step 'clash'.positions.standard.state: 'captured' needs `by: <side id>`",
            "step 'clash'.moves[1].target: unknown unit 'nobody'",
            "step 'clash'.moves[0].continues: {toward: [lon, lat], label?}",
            "step 'clash'.beats[0].label: missing",
            "step 'clash'.beats[2]: needs `positions` or `moves`",
            'alt_sites[1]: {at, label, note?}',
        ] as $expected) {
            $this->assertStringContainsString($expected, $errors);
        }
    }

    public function test_from_and_into_must_reference_units_on_the_field(): void
    {
        $doc = $this->v2();
        $doc['steps'][0]['positions']['blue-horse']['from'] = 'red-foot';
        $doc['steps'][1]['positions']['red-foot'] = ['from' => 'hannibal'];
        $doc['steps'][1]['positions']['blue-horse'] = ['state' => 'hidden'];
        $doc['steps'][1]['beats'][0]['positions']['red-wing']['into'] = 'blue-horse';

        $errors = implode("\n", MapStoryDocument::errors($doc));

        foreach ([
            "step 'deploy'.positions.blue-horse.from: 'red-foot' was not on the field in the previous step",
            "step 'clash'.positions.red-foot.from: red-foot is already on the field — `from` goes on its first placement",
            "step 'clash'.beats[0].positions.red-wing.into: 'blue-horse' is not on the field in this step",
        ] as $expected) {
            $this->assertStringContainsString($expected, $errors);
        }
    }

    public function test_a_valid_schema_3_document_has_no_errors(): void
    {
        $this->assertSame([], MapStoryDocument::errors($this->v3()));
        $this->assertSame([], MapStoryDocument::errors(json_decode(json_encode(MapStoryFixture::chronicleLayer()), true)));
    }

    public function test_a_schema_2_document_using_schema_3_fields_is_told_to_bump_the_schema(): void
    {
        $doc = $this->v3();
        $doc['schema'] = 2;

        $errors = implode("\n", MapStoryDocument::errors($doc));

        foreach ([
            "kind: 'epidemic' needs schema 3 — bump schema to 3",
            'document: ambient, legend, features need schema 3',
            "units[0] (galleys).kind: 'merchant_ship' needs schema 3",
            'units[0] (galleys).side: unknown side',
            "features[1] (sea-lane).kind: 'route' needs schema 3",
            'features[1] (sea-lane): goods, route_kind, active need schema 3',
            "step 's1': date, entities, features need schema 3",
            "step 's1'.features.caffa: value_n, value_label need schema 3",
            "step 's1'.features.caffa.state: 'infected' needs schema 3",
            "step 's2'.features.plague: intensity, area need schema 3",
            "step 's2'.moves[0].type: 'spread' needs schema 3",
        ] as $expected) {
            $this->assertStringContainsString($expected, $errors);
        }
    }

    public function test_a_schema_2_document_may_not_use_a_list_of_rings(): void
    {
        $doc = $this->v2();
        $doc['terrain'][2]['area'] = [$doc['terrain'][2]['area'], $doc['terrain'][2]['area']];

        $this->assertContains('terrain[2] (fill).area: a list of rings needs schema 3 — bump schema to 3', MapStoryDocument::errors($doc));
    }

    public function test_checks_attachment_dates_features_and_step_entities(): void
    {
        $doc = $this->v3();
        unset($doc['entity']);
        $doc['period'] = ['start' => ['year' => 1350], 'end' => ['year' => 1346]];
        $doc['legend'][] = ['swatch' => 'red', 'label' => 'Red'];
        $doc['units'][] = ['id' => 'ghost', 'side' => 'nobody', 'kind' => 'group', 'label' => 'Ghosts'];
        $doc['features'][1]['route_kind'] = 'teleport';
        $doc['features'][2]['route_kind'] = 'trade';
        unset($doc['features'][2]['region_kind']);
        $doc['features'][0]['goods'] = ['grain', 7];
        $doc['features'][0]['intensity'] = 2;
        $doc['features'][0]['side'] = 'genoa';
        $doc['features'][0]['entity'] = ['wikidata' => 'Q130231'];
        unset($doc['steps'][2]['date']);
        $doc['steps'][0]['date'] = ['year' => 1346, 'day' => 3];
        $doc['steps'][1]['date']['end'] = ['year' => 1347, 'month' => 2];
        $doc['steps'][1]['entry'] = 3;
        $doc['steps'][1]['entities'] = [['wikidata' => 'Q1', 'show' => 'yes']];
        $doc['steps'][0]['features']['caffa']['area'] = [[1, 1], [2, 2], [3, 1]];
        $doc['steps'][0]['features']['horde']['area_from_entity'] = ['name' => 'The Horde'];
        $doc['steps'][0]['features']['town'] = ['area_from_entity' => ['wikidata' => 'Q1']];
        $doc['steps'][1]['features']['plague']['value_n'] = -1;
        $doc['steps'][1]['terrain_state'] = [];

        $errors = implode("\n", MapStoryDocument::errors($doc));

        foreach ([
            'entity or chronicle: a story belongs to an entity {name, wikidata?} or a chronicle {slug}',
            'period.end: before the start',
            'legend[1]: {swatch: #rrggbb, label, style?}',
            "units[1] (ghost).side: unknown side 'nobody'",
            'features[1] (sea-lane).route_kind: a route needs one of trade, voyage',
            'features[2] (plague).region_kind: a region needs one of spread',
            'features[2] (plague).route_kind: only a route has one',
            'features[0] (caffa).goods: a list of short names',
            'features[0] (caffa).intensity: a number 0–1',
            "features[0] (caffa).side: unknown side 'genoa'",
            'features[0] (caffa).entity.name: missing',
            "step 's3'.date: an ambient story dates every step",
            "step 's1'.date.day: needs a month",
            "step 's2'.date.end: before the start",
            "step 's2'.entry: only a chronicle's story keys steps to entries",
            "step 's2'.entities[0].name: missing",
            "step 's2'.entities[0].show: true or false",
            "step 's1'.features.caffa.area: a ring or a list of rings, on an area feature only",
            "step 's1'.features.horde.area_from_entity: {wikidata} or {entity_id}",
            "step 's1'.features.town.area_from_entity: on an area feature only",
            "step 's2'.features.plague.value_n: a number ≥ 0",
            "step 's2': features and terrain_state: give one",
        ] as $expected) {
            $this->assertStringContainsString($expected, $errors);
        }
    }

    public function test_checks_chronicle_entries(): void
    {
        $doc = json_decode(json_encode(MapStoryFixture::chronicleLayer(entries: [0, 0])), true);
        $doc['chronicle'] = ['slug' => 'Not A Slug'];
        $doc['steps'][0]['entry'] = -1;

        $errors = implode("\n", MapStoryDocument::errors($doc));

        $this->assertStringContainsString('chronicle: {slug} of an existing chronicle', $errors);
        $this->assertStringContainsString("step 's1'.entry: the entry's sequence_order as stored, an integer ≥ 0", $errors);
        $this->assertStringNotContainsString("step 's2'.entry: entry 0 already has a step", $errors);

        $doc['steps'][0]['entry'] = 0;
        $this->assertContains("step 's2'.entry: entry 0 already has a step", MapStoryDocument::errors($doc));
    }

    public function test_features_and_terrain_are_one_list_under_two_names(): void
    {
        $doc = $this->v3();
        $doc['terrain'] = $doc['features'];

        $this->assertContains('features and terrain: give one (terrain is the old name of features)', MapStoryDocument::errors($doc));

        unset($doc['features']);
        foreach ($doc['steps'] as $i => $step) {
            $doc['steps'][$i]['terrain_state'] = $step['features'];
            unset($doc['steps'][$i]['features']);
        }
        $this->assertSame([], MapStoryDocument::errors($doc));
    }

    public function test_rejects_a_non_object(): void
    {
        $this->assertSame(['document must be an object'], MapStoryDocument::errors([1, 2]));
        $this->assertSame(['document must be an object'], MapStoryDocument::errors('nope'));
    }

    /** @return array<string, mixed> the v3 fixture as the API decodes it */
    private function v3(): array
    {
        return json_decode(json_encode(MapStoryFixture::v3Document()), true);
    }

    /** @return array<string, mixed> the v2 fixture as the API decodes it */
    private function v2(): array
    {
        return json_decode(json_encode(MapStoryFixture::v2Document()), true);
    }
}
