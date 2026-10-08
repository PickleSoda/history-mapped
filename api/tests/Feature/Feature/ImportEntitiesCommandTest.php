<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Enums\VerificationStatus;
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

    /**
     * @param  array<string, mixed>  $overrides
     * @return array<string, mixed>
     */
    private function geoResolutionManifest(array $overrides = []): array
    {
        $manifest = [
            'status' => 'matched',
            'geo_ref' => [
                'provider' => 'ohm',
                'external_type' => 'relation',
                'external_id' => '1880',
                'match_role' => 'primary',
                'retrieval_method' => 'nominatim',
                'match_score' => 1.0,
                'external_tags' => [
                    'historic' => 'empire',
                ],
                'source_meta' => [
                    'display_name' => 'Roman Empire',
                    'class' => 'boundary',
                    'type' => 'historic',
                    'lat' => '41.9',
                    'lon' => '12.5',
                ],
            ],
            'geometry' => [
                'type' => 'Polygon',
                'coordinates' => [[[12.0, 41.0], [13.0, 41.0], [13.0, 42.0], [12.0, 42.0], [12.0, 41.0]]],
            ],
            'provenance' => [
                'resolver' => 'ohm_nominatim',
                'query' => 'Roman Empire Rome',
                'candidates' => 1,
                'reason' => 'exact_name_match',
            ],
        ];

        return array_replace_recursive($manifest, $overrides);
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

    public function test_sync_import_consumes_pipeline_geo_resolution_manifest(): void
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
            '_geo_resolution' => $this->geoResolutionManifest(),
        ];

        file_put_contents($this->jsonlFile, json_encode($record)."\n");

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

        $entity->refresh()->load('primaryLocation');
        $this->assertNotNull($entity->primary_geo_ref_id);
        $this->assertIsArray($entity->primaryLocation?->territory_geom);
        $this->assertSame('Polygon', $entity->primaryLocation?->territory_geom['type'] ?? null);
        $this->assertDatabaseHas('entities', [
            'entity_id' => $entity->entity_id,
            'location_method' => 'ohm_nominatim',
        ]);
    }

    private function importRecord(array $record): void
    {
        file_put_contents($this->jsonlFile, json_encode($record)."\n");

        $this->artisan('pipeline:import', [
            'path' => $this->jsonlFile,
            '--sync' => true,
            '--skip-relationships' => true,
        ])->assertExitCode(0);
    }

    public function test_unverified_pipeline_record_keeps_needs_review_and_its_flags(): void
    {
        // Campaign approval gate: committed without a vetted QID/geometry.
        $this->importRecord([
            'name' => 'Amphipolis',
            'entity_type' => 'city',
            'entity_group' => 'PLACE',
            'summary' => 'A city in Macedonia.',
            'verification_status' => 'needs_review',
            'validation_flags' => ['no_wikidata_match', 'missing_geometry'],
        ]);

        $entity = Entity::query()->where('name', 'Amphipolis')->firstOrFail();
        $this->assertSame(VerificationStatus::NeedsReview, $entity->verification_status);
        $this->assertSame(['no_wikidata_match', 'missing_geometry'], $entity->getAttribute('attributes')['validation_flags'] ?? null);
    }

    public function test_person_with_sign_split_lifespan_is_held_for_review(): void
    {
        // Bagrat IV of Georgia (1018-1072) arrived as "-1015".."1072": a stray minus.
        $this->importRecord([
            'name' => 'Bagrat IV',
            'entity_type' => 'person',
            'entity_group' => 'POLITY',
            'summary' => 'King of Georgia.',
            'temporal_start' => '-1015',
            'temporal_end' => '1072',
        ]);

        $entity = Entity::query()->where('name', 'Bagrat IV')->firstOrFail();
        $this->assertSame(VerificationStatus::NeedsReview, $entity->verification_status);
        $this->assertSame([ImportEntityJob::IMPLAUSIBLE_LIFESPAN_FLAG], $entity->getAttribute('attributes')['validation_flags'] ?? null);
        $this->assertSame(-1015, $entity->primaryTemporalRange?->start_year);
    }

    public function test_person_spanning_year_zero_within_a_lifetime_is_not_flagged(): void
    {
        $this->importRecord([
            'name' => 'Augustus',
            'entity_type' => 'person',
            'entity_group' => 'POLITY',
            'summary' => 'First Roman emperor.',
            'temporal_start' => '-63',
            'temporal_end' => '14',
        ]);

        $entity = Entity::query()->where('name', 'Augustus')->firstOrFail();
        $this->assertSame(VerificationStatus::PipelineDraft, $entity->verification_status);
        $this->assertNull($entity->getAttribute('attributes')['validation_flags'] ?? null);
        $this->assertSame([-63, 14], [$entity->primaryTemporalRange?->start_year, $entity->primaryTemporalRange?->end_year]);
    }

    public function test_pipeline_record_cannot_self_promote_its_status(): void
    {
        $this->importRecord(array_replace($this->record, ['verification_status' => 'human_verified']));

        $entity = Entity::query()->where('wikidata_id', 'Q1059758')->firstOrFail();
        $this->assertSame(VerificationStatus::PipelineDraft, $entity->verification_status);
    }

    public function test_dedup_by_ohm_external_id_when_wikidata_differs(): void
    {
        $base = [
            'name' => 'Roman Empire',
            'entity_type' => 'political_entity',
            'entity_group' => 'POLITY',
            'wikidata_id' => 'Q2277',
            'summary' => 'first',
            'location_name' => 'Rome',
            'verification_status' => 'pipeline_draft',
            'confidence' => 'medium',
            '_geo_resolution' => $this->geoResolutionManifest(),
        ];
        $this->importRecord($base);

        // Same OHM feature (external_id 1880) but a DIFFERENT Wikidata id — this is
        // the cross-transcript case that used to create a duplicate.
        $this->importRecord(array_replace($base, ['wikidata_id' => 'Q9999999', 'summary' => 'second']));

        $this->assertDatabaseCount('entities', 1);
        $this->assertDatabaseHas('entities', ['name' => 'Roman Empire', 'summary' => 'first']);
    }

    public function test_dedup_by_name_and_overlapping_era_when_wikidata_differs(): void
    {
        $first = [
            'name' => 'Deutsches Reich',
            'entity_type' => 'political_entity',
            'entity_group' => 'POLITY',
            'wikidata_id' => 'Q43287',
            'summary' => 'german empire',
            'temporal_start' => '1871',
            'temporal_end' => '1918',
            'verification_status' => 'pipeline_draft',
            'confidence' => 'medium',
        ];
        $this->importRecord($first);

        // Same name + type + overlapping era, different QID -> merge (no new row).
        $this->importRecord(array_replace($first, ['wikidata_id' => 'Q139911734', 'summary' => 'dup']));

        $this->assertDatabaseCount('entities', 1);
    }

    public function test_keeps_distinct_era_namesakes(): void
    {
        $german = [
            'name' => 'Deutsches Reich',
            'entity_type' => 'political_entity',
            'entity_group' => 'POLITY',
            'wikidata_id' => 'Q43287',
            'summary' => 'german empire',
            'temporal_start' => '1871',
            'temporal_end' => '1918',
            'verification_status' => 'pipeline_draft',
            'confidence' => 'medium',
        ];
        $this->importRecord($german);

        // Same name but a non-overlapping era (Nazi Germany) -> kept separate.
        $this->importRecord(array_replace($german, [
            'wikidata_id' => 'Q7318',
            'summary' => 'nazi germany',
            'temporal_start' => '1933',
            'temporal_end' => '1945',
        ]));

        $this->assertDatabaseCount('entities', 2);
    }

    /**
     * @return array<string, mixed>
     */
    private function warRecord(string $name, string $qid, string $summary): array
    {
        return [
            'name' => $name,
            'entity_type' => 'event_war',
            'entity_group' => 'EVENT',
            'wikidata_id' => $qid,
            'summary' => $summary,
            'verification_status' => 'pipeline_draft',
            'confidence' => 'medium',
        ];
    }

    private function importForced(array $record, bool $force = true): void
    {
        file_put_contents($this->jsonlFile, json_encode($record)."\n");

        $this->artisan('pipeline:import', [
            'path' => $this->jsonlFile,
            '--sync' => true,
            '--skip-relationships' => true,
            '--force' => $force,
        ])->assertExitCode(0);
    }

    public function test_force_never_merges_by_qid_into_a_differently_named_row(): void
    {
        $ww2 = Entity::factory()->create([
            'name' => 'World War II',
            'wikidata_id' => 'Q362',
            'summary' => 'Global war 1939-1945.',
        ]);

        // The pipeline gave World War I World War II's QID.
        $this->importForced($this->warRecord('World War I', 'Q362', 'Global war 1914-1918.'));

        $ww2->refresh();
        $this->assertSame('World War II', $ww2->name);
        $this->assertSame('Global war 1939-1945.', $ww2->summary);

        $ww1 = Entity::query()->where('name', 'World War I')->firstOrFail();
        $this->assertNotSame($ww2->entity_id, $ww1->entity_id);
        $this->assertNull($ww1->wikidata_id);
        $this->assertSame('Q362', $ww1->getAttribute('attributes')['_rejected_wikidata_id'] ?? null);
        $this->assertSame(1, Entity::query()->where('wikidata_id', 'Q362')->count());
    }

    public function test_wrong_qid_record_is_not_skipped_as_a_duplicate_without_force(): void
    {
        Entity::factory()->create(['name' => 'World War II', 'wikidata_id' => 'Q362']);

        $this->importForced($this->warRecord('World War I', 'Q362', 'Global war 1914-1918.'), force: false);

        $this->assertDatabaseHas('entities', ['name' => 'World War I', 'wikidata_id' => null]);
        $this->assertDatabaseCount('entities', 2);
    }

    public function test_qid_merge_still_happens_when_an_alias_names_the_row(): void
    {
        $row = Entity::factory()->create([
            'name' => 'Yongle Emperor',
            'wikidata_id' => 'Q9726',
            'summary' => 'Third Ming emperor.',
        ]);

        $record = array_replace($this->warRecord('Zhu Di', 'Q9726', 'Ming emperor who moved the capital.'), [
            'entity_type' => 'person',
            'entity_group' => 'POLITY',
            'alternative_names' => ['Yongle Emperor'],
        ]);
        $this->importForced($record);

        $this->assertDatabaseCount('entities', 1);
        $this->assertSame('Ming emperor who moved the capital.', $row->refresh()->summary);
    }

    public function test_ohm_id_merge_is_name_guarded(): void
    {
        $romania = [
            'name' => 'Romania',
            'entity_type' => 'political_entity',
            'entity_group' => 'POLITY',
            'wikidata_id' => 'Q218',
            'summary' => 'Balkan state.',
            'alternative_names' => ['Romagne'],
            'verification_status' => 'pipeline_draft',
            'confidence' => 'medium',
            '_geo_resolution' => $this->geoResolutionManifest([
                'geo_ref' => ['external_id' => '2851901', 'source_meta' => ['display_name' => 'Romagne, Imperium Romanum']],
            ]),
        ];
        $this->importRecord($romania);

        // Same OHM feature, different polity: the shared OHM alias is no evidence.
        $this->importForced(array_replace($romania, [
            'name' => 'Romagna',
            'wikidata_id' => 'Q1952',
            'summary' => 'Italian region.',
        ]));

        $this->assertDatabaseCount('entities', 2);
        $this->assertDatabaseHas('entities', ['name' => 'Romania', 'summary' => 'Balkan state.']);
        $this->assertDatabaseHas('entities', ['name' => 'Romagna', 'wikidata_id' => 'Q1952']);
    }

    public function test_sync_import_skips_geo_ref_creation_when_manifest_reports_no_match(): void
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
            '_geo_resolution' => $this->geoResolutionManifest([
                'status' => 'no_match',
                'geo_ref' => null,
                'geometry' => null,
                'provenance' => [
                    'candidates' => 2,
                    'reason' => 'no_exact_name_match',
                ],
            ]),
        ];

        file_put_contents($this->jsonlFile, json_encode($record)."\n");

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
