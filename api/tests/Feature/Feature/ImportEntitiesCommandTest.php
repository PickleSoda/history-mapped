<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Jobs\ImportEntityJob;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
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
}
