<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Models\GeometryPeriod;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ImportBordersCommandTest extends TestCase
{
    use RefreshDatabase;

    /**
     * @param  array<string, mixed>  $overrides
     * @return array<string, mixed>
     */
    private function makeRecord(array $overrides = []): array
    {
        return array_replace_recursive([
            'name' => 'Testland',
            'entity_type' => 'political_entity',
            'entity_group' => 'POLITY',
            'wikidata_id' => 'Q9999',
            'summary' => 'A test polity',
            'temporal_start' => '1900',
            'temporal_end' => '1950',
            'verification_status' => 'ohm_draft',
            'confidence' => 'medium',
            'location_method' => 'ohm_nominatim',
            'location_confidence' => 'high',
            '_ohm_relation_id' => '100',
            '_geometry_periods' => [
                [
                    'ohm_relation_id' => '100',
                    'external_type' => 'relation',
                    'start_year' => 1900,
                    'end_year' => 1950,
                    'start_date' => '1900',
                    'end_date' => '1950',
                    'geojson' => [
                        'type' => 'MultiPolygon',
                        'coordinates' => [[[[0, 0], [1, 0], [1, 1], [0, 0]]]],
                    ],
                    'label' => 'Testland (1900-1950)',
                    'external_tags' => ['name' => 'Testland'],
                ],
            ],
        ], $overrides);
    }

    public function test_command_imports_single_jsonl_record_sync(): void
    {
        $record = $this->makeRecord(['wikidata_id' => 'Q7777']);
        $path = $this->writeTemp(json_encode($record)."\n");

        $this->artisan('pipeline:import-borders', [
            'path' => $path,
            '--sync' => true,
        ])->assertExitCode(0);

        $entity = Entity::query()->where('wikidata_id', 'Q7777')->first();
        $this->assertNotNull($entity);
        $this->assertSame('ohm_draft', $entity->verification_status->value);

        $this->assertDatabaseHas('entity_geo_refs', [
            'entity_id' => $entity->entity_id,
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => '100',
        ]);

        $geoRefs = EntityGeoRef::query()->where('entity_id', $entity->entity_id)->get();
        $this->assertCount(2, $geoRefs);
        $this->assertCount(1, $geoRefs->whereNull('geometry_period_id'));
        $this->assertCount(1, $geoRefs->whereNotNull('geometry_period_id'));
    }

    public function test_command_is_idempotent_for_duplicate_lines(): void
    {
        $record = $this->makeRecord(['wikidata_id' => 'Q6666']);
        $jsonl = json_encode($record)."\n".json_encode($record)."\n";
        $path = $this->writeTemp($jsonl);

        $this->artisan('pipeline:import-borders', [
            'path' => $path,
            '--sync' => true,
        ])->assertExitCode(0);

        $entity = Entity::query()->where('wikidata_id', 'Q6666')->firstOrFail();

        $this->assertCount(1, Entity::query()->where('wikidata_id', 'Q6666')->get());
        $this->assertCount(1, GeometryPeriod::query()->where('entity_id', $entity->entity_id)->get());
        $this->assertCount(2, EntityGeoRef::query()->where('entity_id', $entity->entity_id)->get());
    }

    public function test_command_creates_geometry_period_for_each_stage(): void
    {
        $record = $this->makeRecord([
            'wikidata_id' => 'Q8888',
            '_ohm_relation_id' => '200',
            '_geometry_periods' => [
                [
                    'ohm_relation_id' => '201',
                    'external_type' => 'relation',
                    'start_year' => 1800,
                    'end_year' => 1850,
                    'geojson' => [
                        'type' => 'MultiPolygon',
                        'coordinates' => [[[[0, 0], [2, 0], [2, 2], [0, 0]]]],
                    ],
                    'label' => 'Evolving (1800-1850)',
                    'external_tags' => [],
                ],
                [
                    'ohm_relation_id' => '202',
                    'external_type' => 'relation',
                    'start_year' => 1850,
                    'end_year' => 1900,
                    'geojson' => [
                        'type' => 'MultiPolygon',
                        'coordinates' => [[[[0, 0], [3, 0], [3, 3], [0, 0]]]],
                    ],
                    'label' => 'Evolving (1850-1900)',
                    'external_tags' => [],
                ],
            ],
        ]);

        $path = $this->writeTemp(json_encode($record)."\n");

        $this->artisan('pipeline:import-borders', [
            'path' => $path,
            '--sync' => true,
        ])->assertExitCode(0);

        $entity = Entity::query()->where('wikidata_id', 'Q8888')->firstOrFail();
        $periods = GeometryPeriod::query()->where('entity_id', $entity->entity_id)->get();
        $geoRefs = EntityGeoRef::query()->where('entity_id', $entity->entity_id)->get();

        $this->assertCount(2, $periods);
        $this->assertSame([1800, 1850], $periods->pluck('start_year')->sort()->values()->all());
        $this->assertCount(3, $geoRefs);
        $this->assertSame(
            ['200', '201', '202'],
            $geoRefs->pluck('external_id')->sort()->values()->all(),
        );
        $this->assertCount(2, $geoRefs->whereNotNull('geometry_period_id'));
        $this->assertCount(1, $geoRefs->whereNull('geometry_period_id'));
    }

    public function test_command_sorts_geo_ref_temporal_bounds_when_geometry_periods_are_unordered(): void
    {
        $record = $this->makeRecord([
            'wikidata_id' => 'Q1619',
            'temporal_start' => '1619',
            'temporal_end' => '1620',
            '_ohm_relation_id' => '2847638',
            '_geometry_periods' => [
                [
                    'ohm_relation_id' => '2847638',
                    'external_type' => 'relation',
                    'start_year' => 1620,
                    'end_year' => 1620,
                    'start_date' => '1620',
                    'end_date' => '1620',
                    'geojson' => [
                        'type' => 'MultiPolygon',
                        'coordinates' => [[[[0, 0], [2, 0], [2, 2], [0, 0]]]],
                    ],
                    'label' => 'Later stage',
                    'external_tags' => [],
                ],
                [
                    'ohm_relation_id' => '2847638',
                    'external_type' => 'relation',
                    'start_year' => 1619,
                    'end_year' => 1619,
                    'start_date' => '1619',
                    'end_date' => '1619',
                    'geojson' => [
                        'type' => 'MultiPolygon',
                        'coordinates' => [[[[0, 0], [3, 0], [3, 3], [0, 0]]]],
                    ],
                    'label' => 'Earlier stage',
                    'external_tags' => [],
                ],
            ],
        ]);

        $path = $this->writeTemp(json_encode($record)."\n");

        $this->artisan('pipeline:import-borders', [
            'path' => $path,
            '--sync' => true,
        ])->assertExitCode(0);

        $entity = Entity::query()->where('wikidata_id', 'Q1619')->firstOrFail();
        $geoRef = EntityGeoRef::query()->where('entity_id', $entity->entity_id)->firstOrFail();

        $this->assertSame(1619, $geoRef->temporal_start_year);
        $this->assertSame(1620, $geoRef->temporal_end_year);
        $this->assertSame('1619', $geoRef->temporal_start);
        $this->assertSame('1620', $geoRef->temporal_end);
    }

    public function test_command_skips_invalid_geometry_periods_with_reversed_years(): void
    {
        $record = $this->makeRecord([
            'wikidata_id' => 'Q4948',
            'name' => 'Republic of Venice',
            'temporal_start' => '0697',
            'temporal_end' => '1797',
            '_ohm_relation_id' => '2835819',
            '_geometry_periods' => [
                [
                    'ohm_relation_id' => '2835819',
                    'external_type' => 'relation',
                    'start_year' => 1390,
                    'end_year' => 1363,
                    'start_date' => '1390',
                    'end_date' => '1363',
                    'geojson' => [
                        'type' => 'MultiPolygon',
                        'coordinates' => [[[[0, 0], [2, 0], [2, 2], [0, 0]]]],
                    ],
                    'label' => 'Republic of Venice (1390-1363)',
                    'external_tags' => [],
                ],
                [
                    'ohm_relation_id' => '2835820',
                    'external_type' => 'relation',
                    'start_year' => 1391,
                    'end_year' => 1404,
                    'start_date' => '1391',
                    'end_date' => '1404',
                    'geojson' => [
                        'type' => 'MultiPolygon',
                        'coordinates' => [[[[0, 0], [3, 0], [3, 3], [0, 0]]]],
                    ],
                    'label' => 'Republic of Venice (1391-1404)',
                    'external_tags' => [],
                ],
            ],
        ]);

        $path = $this->writeTemp(json_encode($record)."\n");

        $this->artisan('pipeline:import-borders', [
            'path' => $path,
            '--sync' => true,
        ])->assertExitCode(0);

        $entity = Entity::query()->where('wikidata_id', 'Q4948')->firstOrFail();
        $periods = GeometryPeriod::query()
            ->where('entity_id', $entity->entity_id)
            ->orderBy('start_year')
            ->get();

        $this->assertCount(1, $periods);
        $this->assertSame(1391, $periods[0]->start_year);
        $this->assertSame(1404, $periods[0]->end_year);
        $this->assertSame('Republic of Venice (1391-1404)', $periods[0]->description);
    }

    public function test_command_imports_open_ended_geometry_period(): void
    {
        $record = $this->makeRecord([
            'wikidata_id' => 'Q36',
            'name' => 'Poland',
            'temporal_start' => '1991-03-21',
            'temporal_end' => null,
            '_ohm_relation_id' => '2870169',
            '_geometry_periods' => [
                [
                    'ohm_relation_id' => '2870169',
                    'external_type' => 'relation',
                    'start_year' => 1991,
                    'end_year' => null,
                    'start_date' => '1991-03-21',
                    'end_date' => null,
                    'geojson' => [
                        'type' => 'MultiPolygon',
                        'coordinates' => [[[[0, 0], [1, 0], [1, 1], [0, 0]]]],
                    ],
                    'label' => 'Poland (1991-present)',
                    'external_tags' => ['name' => 'Poland'],
                ],
            ],
        ]);

        $path = $this->writeTemp(json_encode($record)."\n");

        $this->artisan('pipeline:import-borders', [
            'path' => $path,
            '--sync' => true,
        ])->assertExitCode(0);

        $entity = Entity::query()->where('wikidata_id', 'Q36')->firstOrFail();

        $periods = GeometryPeriod::query()
            ->where('entity_id', $entity->entity_id)
            ->get();

        $this->assertCount(1, $periods);
        $this->assertSame(1991, $periods[0]->start_year);
        $this->assertNull($periods[0]->end_year);
    }

    public function test_command_force_updates_existing_entity(): void
    {
        $record = $this->makeRecord([
            'wikidata_id' => 'Q5555',
            'summary' => 'Updated summary via force',
        ]);
        $path = $this->writeTemp(json_encode($record)."\n");

        Entity::factory()->create([
            'wikidata_id' => 'Q5555',
            'name' => 'Testland',
            'entity_type' => 'political_entity',
            'entity_group' => 'POLITY',
            'summary' => 'Original summary',
            'verification_status' => 'pipeline_draft',
        ]);

        $this->artisan('pipeline:import-borders', [
            'path' => $path,
            '--sync' => true,
            '--force' => true,
        ])->assertExitCode(0);

        $entity = Entity::query()->where('wikidata_id', 'Q5555')->firstOrFail();
        $this->assertSame('Updated summary via force', $entity->summary);
        $this->assertSame('ohm_draft', $entity->verification_status->value);
    }

    private function writeTemp(string $content): string
    {
        $path = tempnam(sys_get_temp_dir(), 'import_borders_').'.jsonl';
        file_put_contents($path, $content);

        $this->beforeApplicationDestroyed(function () use ($path): void {
            if (file_exists($path)) {
                unlink($path);
            }
        });

        return $path;
    }
}
