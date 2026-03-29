<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Jobs\ImportEntityJob;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Queue;
use Tests\TestCase;

class ImportEntitiesCommandTest extends TestCase
{
    use RefreshDatabase;

    private string $jsonlFile;

    /** @var array<string, mixed> */
    private array $record;

    protected function setUp(): void
    {
        parent::setUp();

        $this->record = [
            'name' => 'Bronze Age collapse',
            'entity_type' => 'event_war',
            'entity_group' => 'EVENT',
            'wikidata_id' => 'Q1059758',
            'summary' => 'A period of societal collapse.',
            'verification_status' => 'pipeline_draft',
            'confidence' => 'medium',
        ];

        $this->jsonlFile = tempnam(sys_get_temp_dir(), 'import_test_').'.jsonl';
        file_put_contents($this->jsonlFile, json_encode($this->record)."\n");
    }

    protected function tearDown(): void
    {
        parent::tearDown();

        if (file_exists($this->jsonlFile)) {
            unlink($this->jsonlFile);
        }
    }

    public function test_import_creates_entity_when_none_exists(): void
    {
        $this->artisan('pipeline:import', [
            'path' => $this->jsonlFile,
            '--sync' => true,
            '--skip-relationships' => true,
        ])->assertExitCode(0);

        $this->assertDatabaseHas('entities', [
            'wikidata_id' => 'Q1059758',
            'name' => 'Bronze Age collapse',
        ]);
    }

    public function test_import_skips_existing_entity_without_force(): void
    {
        Entity::factory()->create([
            'wikidata_id' => 'Q1059758',
            'name' => 'Bronze Age collapse',
            'summary' => 'Original summary.',
        ]);

        $this->artisan('pipeline:import', [
            'path' => $this->jsonlFile,
            '--sync' => true,
            '--skip-relationships' => true,
        ])->assertExitCode(0);

        $this->assertDatabaseHas('entities', [
            'wikidata_id' => 'Q1059758',
            'summary' => 'Original summary.',
        ]);
    }

    public function test_force_flag_overwrites_existing_entity(): void
    {
        Entity::factory()->create([
            'wikidata_id' => 'Q1059758',
            'name' => 'Bronze Age collapse',
            'summary' => 'Original summary.',
        ]);

        $this->artisan('pipeline:import', [
            'path' => $this->jsonlFile,
            '--sync' => true,
            '--force' => true,
            '--skip-relationships' => true,
        ])->assertExitCode(0);

        $this->assertDatabaseHas('entities', [
            'wikidata_id' => 'Q1059758',
            'summary' => 'A period of societal collapse.',
        ]);

        $this->assertDatabaseCount('entities', 1);
    }

    public function test_force_flag_shows_warning_message(): void
    {
        $this->artisan('pipeline:import', [
            'path' => $this->jsonlFile,
            '--sync' => true,
            '--force' => true,
            '--skip-relationships' => true,
        ])
            ->expectsOutputToContain('Force mode')
            ->assertExitCode(0);
    }

    public function test_force_flag_dispatches_jobs_with_force_true(): void
    {
        Queue::fake();

        $this->artisan('pipeline:import', [
            'path' => $this->jsonlFile,
            '--force' => true,
            '--skip-relationships' => true,
        ])->assertExitCode(0);

        Queue::assertPushed(ImportEntityJob::class, function ($job) {
            return $job->force === true;
        });
    }

    public function test_without_force_flag_dispatches_jobs_with_force_false(): void
    {
        Queue::fake();

        $this->artisan('pipeline:import', [
            'path' => $this->jsonlFile,
            '--skip-relationships' => true,
        ])->assertExitCode(0);

        Queue::assertPushed(ImportEntityJob::class, function ($job) {
            return $job->force === false;
        });
    }

    public function test_sync_import_auto_attaches_deterministic_ohm_reference(): void
    {
        $record = [
            'name' => 'Roman Empire',
            'entity_type' => 'political_entity',
            'entity_group' => 'POLITY',
            'wikidata_id' => 'Q2277',
            'summary' => 'An imperial polity.',
            'location_name' => 'Rome',
            'verification_status' => 'pipeline_draft',
            'confidence' => 'medium',
        ];

        file_put_contents($this->jsonlFile, json_encode($record)."\n");

        Http::fake([
            'https://nominatim.openhistoricalmap.org/search*' => Http::response([
                [
                    'osm_type' => 'relation',
                    'osm_id' => 1880,
                    'display_name' => 'Roman Empire',
                    'geojson' => [
                        'type' => 'Polygon',
                        'coordinates' => [[[12.0, 41.0], [13.0, 41.0], [13.0, 42.0], [12.0, 42.0], [12.0, 41.0]]],
                    ],
                    'extratags' => [
                        'historic' => 'empire',
                    ],
                    'lat' => '41.9',
                    'lon' => '12.5',
                ],
            ], 200),
        ]);

        $this->artisan('pipeline:import', [
            'path' => $this->jsonlFile,
            '--sync' => true,
            '--skip-relationships' => true,
        ])->assertExitCode(0);

        $entity = Entity::query()->where('wikidata_id', 'Q2277')->firstOrFail();

        $this->assertDatabaseHas('entity_geo_refs', [
            'entity_id' => $entity->entity_id,
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => '1880',
            'match_role' => 'primary',
            'is_active' => true,
        ]);

        $entity->refresh();
        $this->assertNotNull($entity->primary_geo_ref_id);
        $this->assertIsArray($entity->territory_geom);
        $this->assertSame('Polygon', $entity->territory_geom['type'] ?? null);
    }

    public function test_sync_import_skips_auto_attach_when_best_name_match_is_not_exact_enough(): void
    {
        $record = [
            'name' => 'Roman Empire',
            'entity_type' => 'political_entity',
            'entity_group' => 'POLITY',
            'wikidata_id' => 'Q2277',
            'summary' => 'An imperial polity.',
            'location_name' => 'Rome',
            'verification_status' => 'pipeline_draft',
            'confidence' => 'medium',
        ];

        file_put_contents($this->jsonlFile, json_encode($record)."\n");

        Http::fake([
            'https://nominatim.openhistoricalmap.org/search*' => Http::response([
                [
                    'osm_type' => 'relation',
                    'osm_id' => 1880,
                    'display_name' => 'Roman Republic',
                    'geojson' => [
                        'type' => 'Polygon',
                        'coordinates' => [[[12.0, 41.0], [13.0, 41.0], [13.0, 42.0], [12.0, 42.0], [12.0, 41.0]]],
                    ],
                ],
                [
                    'osm_type' => 'relation',
                    'osm_id' => 1881,
                    'display_name' => 'Imperial Roman Domain',
                    'geojson' => [
                        'type' => 'Polygon',
                        'coordinates' => [[[12.0, 41.0], [13.0, 41.0], [13.0, 42.0], [12.0, 42.0], [12.0, 41.0]]],
                    ],
                ],
            ], 200),
        ]);

        $this->artisan('pipeline:import', [
            'path' => $this->jsonlFile,
            '--sync' => true,
            '--skip-relationships' => true,
        ])->assertExitCode(0);

        $entity = Entity::query()->where('wikidata_id', 'Q2277')->firstOrFail();

        $this->assertDatabaseMissing('entity_geo_refs', [
            'entity_id' => $entity->entity_id,
            'provider' => 'ohm',
        ]);

        $entity->refresh();
        $this->assertNull($entity->primary_geo_ref_id);
        $this->assertNull($entity->territory_geom);
    }
}
