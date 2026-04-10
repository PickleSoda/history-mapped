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
        $this->assertCount(1, EntityGeoRef::query()->where('entity_id', $entity->entity_id)->get());
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

        $this->assertCount(2, $periods);
        $this->assertSame([1800, 1850], $periods->pluck('start_year')->sort()->values()->all());
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
