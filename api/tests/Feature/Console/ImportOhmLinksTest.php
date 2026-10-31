<?php

declare(strict_types=1);

namespace Tests\Feature\Console;

use App\Actions\EntityGeoRef\CreateEntityGeoRefAction;
use App\Actions\EntityGeoRef\ImportOhmLinksAction;
use App\Enums\GeoRefExternalType;
use App\Enums\GeoRefMatchRole;
use App\Enums\GeoRefProvider;
use App\Enums\GeoRefRetrievalMethod;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Log;
use RuntimeException;
use Tests\TestCase;

class ImportOhmLinksTest extends TestCase
{
    use RefreshDatabase;

    private const TAGS = [
        'boundary' => 'administrative',
        'admin_level' => '2',
        'name' => 'Imperium Romanum',
        'name:en' => 'Roman Empire',
        'wikidata' => 'Q2277',
        'start_date' => '-0027-01-16',
        'end_date' => '0476-09-04',
    ];

    public function test_a_existing_ref_gets_years_raw_dates_and_tags(): void
    {
        $ref = $this->ohmRef(Entity::factory()->create(), 'relation', '1880', [
            'is_active' => false,
            'temporal_start_year' => null,
            'temporal_end_year' => null,
            'external_tags' => null,
        ]);

        $counters = $this->import([$this->record()]);

        $this->assertSame($this->counters(['refs_updated' => 1]), $counters);
        $ref->refresh();
        $this->assertSame(-27, $ref->temporal_start_year);
        $this->assertSame(476, $ref->temporal_end_year);
        $this->assertSame('-0027-01-16', $ref->temporal_start);
        $this->assertSame('0476-09-04', $ref->temporal_end);
        $this->assertEquals(self::TAGS, $ref->external_tags);
        $this->assertFalse($ref->is_active);
    }

    public function test_a_empty_tags_on_an_existing_ref_are_replaced(): void
    {
        $ref = $this->ohmRef(Entity::factory()->create(), 'relation', '1880', [
            'temporal_start_year' => -27,
            'temporal_end_year' => 476,
            'temporal_start' => '-0027-01-16',
            'temporal_end' => '0476-09-04',
            'external_tags' => [],
        ]);

        $counters = $this->import([$this->record()]);

        $this->assertSame($this->counters(['refs_updated' => 1]), $counters);
        $this->assertEquals(self::TAGS, $ref->refresh()->external_tags);
    }

    public function test_b_entity_without_refs_gets_a_primary_ref_by_qid(): void
    {
        $entity = Entity::factory()->create(['wikidata_id' => 'Q2277']);

        $path = $this->writeJsonl([$this->record()]);
        $counters = app(ImportOhmLinksAction::class)($path, 'batch-b', false, false);

        $this->assertSame($this->counters(['refs_created' => 1]), $counters);
        $ref = $this->onlyRef($entity, 'relation', '1880');
        $this->assertSame(GeoRefMatchRole::Primary, $ref->match_role);
        $this->assertTrue($ref->is_active);
        $this->assertSame(GeoRefRetrievalMethod::Overpass, $ref->retrieval_method);
        $this->assertSame('0.9000', $ref->match_score);
        $this->assertSame(-27, $ref->temporal_start_year);
        $this->assertSame(476, $ref->temporal_end_year);
        $this->assertSame('-0027-01-16', $ref->temporal_start);
        $this->assertSame('0476-09-04', $ref->temporal_end);
        $this->assertEquals(self::TAGS, $ref->external_tags);
        $this->assertEquals([
            'source' => 'ohm-links',
            'batch_id' => 'batch-b',
            'run_id' => basename(dirname($path)),
        ], $ref->source_meta);
        $this->assertSame($ref->geo_ref_id, $entity->refresh()->primary_geo_ref_id);
    }

    public function test_c_entity_with_an_active_primary_of_another_provider_gets_a_candidate(): void
    {
        $entity = Entity::factory()->create(['wikidata_id' => 'Q2277']);
        $existing = EntityGeoRef::factory()->forEntity($entity)->primary()->create([
            'provider' => GeoRefProvider::Wikidata->value,
            'external_type' => GeoRefExternalType::Qid->value,
            'external_id' => 'Q2277',
        ]);
        $entity->forceFill(['primary_geo_ref_id' => $existing->geo_ref_id])->save();

        $counters = $this->import([$this->record()]);

        $this->assertSame($this->counters(['refs_created' => 1]), $counters);
        $ref = $this->onlyRef($entity, 'relation', '1880');
        $this->assertSame(GeoRefMatchRole::Candidate, $ref->match_role);
        $this->assertTrue($ref->is_active);
        $this->assertTrue($existing->refresh()->is_active);
        $this->assertSame(GeoRefMatchRole::Primary, $existing->match_role);
        $this->assertSame($existing->geo_ref_id, $entity->refresh()->primary_geo_ref_id);
    }

    public function test_d_two_entities_sharing_a_qid_both_get_refs(): void
    {
        $first = Entity::factory()->create(['wikidata_id' => 'Q2277']);
        $second = Entity::factory()->create(['wikidata_id' => 'Q2277']);

        $counters = $this->import([$this->record()]);

        $this->assertSame($this->counters(['refs_created' => 2, 'qid_duplicates' => 1]), $counters);
        foreach ([$first, $second] as $entity) {
            $ref = $this->onlyRef($entity, 'relation', '1880');
            $this->assertSame(GeoRefMatchRole::Primary, $ref->match_role);
            $this->assertSame($ref->geo_ref_id, $entity->refresh()->primary_geo_ref_id);
        }
    }

    public function test_e_dry_run_rolls_back_inserts_updates_and_primary_changes(): void
    {
        $entity = Entity::factory()->create(['wikidata_id' => 'Q2277']);
        $existing = $this->ohmRef(Entity::factory()->create(), 'relation', '1880', [
            'temporal_start_year' => null,
            'temporal_end_year' => null,
            'external_tags' => null,
        ]);
        $path = $this->writeJsonl([$this->record()]);

        $this->artisan('pipeline:import-ohm-links', ['path' => $path, '--dry-run' => true])
            ->expectsTable(['Counter', 'Value'], $this->tableRows($this->counters(['refs_updated' => 1, 'refs_created' => 1])))
            ->assertExitCode(0);

        $this->assertSame(1, EntityGeoRef::query()->count());
        $existing->refresh();
        $this->assertNull($existing->temporal_start_year);
        $this->assertNull($existing->temporal_end_year);
        $this->assertNull($existing->temporal_start);
        $this->assertNull($existing->temporal_end);
        $this->assertNull($existing->external_tags);
        $this->assertNull($entity->refresh()->primary_geo_ref_id);
    }

    public function test_f_record_without_qid_or_existing_ref_is_unmatched(): void
    {
        Entity::factory()->create(['wikidata_id' => 'Q2277']);

        $counters = $this->import([$this->record(['wikidata_id' => null])]);

        $this->assertSame($this->counters(['unmatched' => 1]), $counters);
        $this->assertSame(0, EntityGeoRef::query()->count());
    }

    public function test_g_overwrite_years_replaces_non_null_years_and_the_default_does_not(): void
    {
        $ref = $this->ohmRef(Entity::factory()->create(), 'relation', '1880', [
            'temporal_start_year' => 100,
            'temporal_end_year' => 200,
            'temporal_start' => '0100',
            'temporal_end' => '0200',
        ]);
        $path = $this->writeJsonl([$this->record()]);

        $this->artisan('pipeline:import-ohm-links', ['path' => $path])
            ->expectsTable(['Counter', 'Value'], $this->tableRows($this->counters()))
            ->assertExitCode(0);

        $ref->refresh();
        $this->assertSame([100, 200, '0100', '0200'], [$ref->temporal_start_year, $ref->temporal_end_year, $ref->temporal_start, $ref->temporal_end]);

        $this->artisan('pipeline:import-ohm-links', ['path' => $path, '--overwrite-years' => true])
            ->expectsTable(['Counter', 'Value'], $this->tableRows($this->counters(['refs_updated' => 1])))
            ->assertExitCode(0);

        // The raw strings follow the replaced years, so the columns cannot disagree.
        $ref->refresh();
        $this->assertSame([-27, 476, '-0027-01-16', '0476-09-04'], [$ref->temporal_start_year, $ref->temporal_end_year, $ref->temporal_start, $ref->temporal_end]);
    }

    public function test_h_start_after_end_stores_no_years_but_keeps_the_raw_dates(): void
    {
        $existing = $this->ohmRef(Entity::factory()->create(), 'relation', '2851494', [
            'temporal_start_year' => null,
            'temporal_end_year' => null,
            'temporal_start' => null,
            'temporal_end' => null,
        ]);
        $entity = Entity::factory()->create(['wikidata_id' => 'Q2277']);

        $counters = $this->import([$this->record([
            'osm_id' => 2851494,
            'start_date' => '1947',
            'end_date' => '1600',
        ])]);

        $this->assertSame($this->counters(['refs_updated' => 1, 'refs_created' => 1, 'invalid_years' => 1]), $counters);
        foreach ([$existing->refresh(), $this->onlyRef($entity, 'relation', '2851494')] as $ref) {
            $this->assertNull($ref->temporal_start_year);
            $this->assertNull($ref->temporal_end_year);
            $this->assertSame('1947', $ref->temporal_start);
            $this->assertSame('1600', $ref->temporal_end);
        }
    }

    public function test_i_inactive_ref_on_the_entity_is_skipped_and_not_reactivated(): void
    {
        $entity = Entity::factory()->create(['wikidata_id' => 'Q2277']);
        $inactive = $this->ohmRef($entity, 'relation', '1880', [
            'is_active' => false,
            'temporal_start_year' => -27,
            'temporal_end_year' => 476,
            'temporal_start' => '-0027-01-16',
            'temporal_end' => '0476-09-04',
            'external_tags' => self::TAGS,
        ]);

        $counters = $this->import([$this->record()]);

        $this->assertSame($this->counters(['skipped_existing' => 1]), $counters);
        $this->assertSame(1, EntityGeoRef::query()->where('entity_id', $entity->entity_id)->count());
        $this->assertFalse($inactive->refresh()->is_active);
        $this->assertNull($entity->refresh()->primary_geo_ref_id);
    }

    public function test_j_several_features_for_one_qid_pick_a_deterministic_primary(): void
    {
        $entity = Entity::factory()->withTemporalRange('1800', '1900')->create(['wikidata_id' => 'Q2277']);

        $counters = $this->import([
            $this->record(['osm_type' => 'node', 'osm_id' => 1, 'start_date' => '1700', 'end_date' => '1900']),
            $this->record(['osm_type' => 'relation', 'osm_id' => 9, 'start_date' => '1890', 'end_date' => '1950']),
            $this->record(['osm_type' => 'relation', 'osm_id' => 5, 'start_date' => '1780', 'end_date' => '1850']),
        ]);

        $this->assertSame($this->counters(['records' => 3, 'refs_created' => 3]), $counters);
        $primary = $this->onlyRef($entity, 'relation', '5');
        $this->assertSame(GeoRefMatchRole::Primary, $primary->match_role);
        $this->assertSame($primary->geo_ref_id, $entity->refresh()->primary_geo_ref_id);
        $this->assertSame(GeoRefMatchRole::Candidate, $this->onlyRef($entity, 'relation', '9')->match_role);
        $this->assertSame(GeoRefMatchRole::Candidate, $this->onlyRef($entity, 'node', '1')->match_role);
    }

    public function test_undated_records_rank_after_dated_ones_before_overlap(): void
    {
        // Open bounds would give the undated relation/3 the same overlap as relation/7 and,
        // as "ongoing", the latest end; it must still lose to the dated feature.
        $entity = Entity::factory()->withTemporalRange('1800', '1900')->create(['wikidata_id' => 'Q2277']);

        $counters = $this->import([
            $this->record(['osm_id' => 3, 'start_date' => null, 'end_date' => null]),
            $this->record(['osm_id' => 2, 'start_date' => '1947', 'end_date' => '1600']),
            $this->record(['osm_id' => 7, 'start_date' => '1800', 'end_date' => '1900']),
        ]);

        $this->assertSame($this->counters(['records' => 3, 'refs_created' => 3, 'invalid_years' => 1]), $counters);
        $this->assertSame(GeoRefMatchRole::Primary, $this->onlyRef($entity, 'relation', '7')->match_role);
        $this->assertSame(GeoRefMatchRole::Candidate, $this->onlyRef($entity, 'relation', '3')->match_role);
        $this->assertSame(GeoRefMatchRole::Candidate, $this->onlyRef($entity, 'relation', '2')->match_role);
    }

    public function test_latest_end_breaks_overlap_ties_by_year_then_raw_date_with_open_end_latest(): void
    {
        $byDate = Entity::factory()->withTemporalRange('1800', '1900')->create(['wikidata_id' => 'Q1']);
        $byOpenEnd = Entity::factory()->withTemporalRange('1800', '1900')->create(['wikidata_id' => 'Q2']);

        $this->import([
            $this->record(['wikidata_id' => 'Q1', 'osm_id' => 4, 'start_date' => '1800-01-01', 'end_date' => '1850-11-30']),
            $this->record(['wikidata_id' => 'Q1', 'osm_id' => 8, 'start_date' => '1800-01-01', 'end_date' => '1850-03-01']),
            $this->record(['wikidata_id' => 'Q1', 'osm_id' => 6, 'start_date' => '1800-01-01', 'end_date' => '1850-12-31']),
            $this->record(['wikidata_id' => 'Q2', 'osm_id' => 14, 'start_date' => '1800', 'end_date' => '1950']),
            $this->record(['wikidata_id' => 'Q2', 'osm_id' => 18, 'start_date' => '1800', 'end_date' => null]),
        ]);

        $this->assertSame(GeoRefMatchRole::Primary, $this->onlyRef($byDate, 'relation', '6')->match_role);
        $this->assertSame(GeoRefMatchRole::Candidate, $this->onlyRef($byDate, 'relation', '4')->match_role);
        $this->assertSame(GeoRefMatchRole::Primary, $this->onlyRef($byOpenEnd, 'relation', '18')->match_role);
        $this->assertSame(GeoRefMatchRole::Candidate, $this->onlyRef($byOpenEnd, 'relation', '14')->match_role);
    }

    public function test_run_id_option_is_stored_in_source_meta(): void
    {
        $entity = Entity::factory()->create(['wikidata_id' => 'Q2277']);
        $path = $this->writeJsonl([$this->record()]);

        $this->artisan('pipeline:import-ohm-links', ['path' => $path, '--run-id' => '20261031-1200', '--batch-id' => 'b1'])
            ->assertExitCode(0);

        $this->assertEquals(
            ['source' => 'ohm-links', 'batch_id' => 'b1', 'run_id' => '20261031-1200'],
            $this->onlyRef($entity, 'relation', '1880')->source_meta,
        );
    }

    public function test_a_rerun_of_the_same_file_is_idempotent(): void
    {
        $entity = Entity::factory()->create(['wikidata_id' => 'Q2277']);
        $this->ohmRef(Entity::factory()->create(), 'relation', '1880', [
            'temporal_start_year' => null,
            'temporal_end_year' => null,
            'external_tags' => null,
        ]);
        $path = $this->writeJsonl([
            $this->record(),
            $this->record(['osm_type' => 'node', 'osm_id' => 5, 'start_date' => '1800', 'end_date' => '1900']),
        ]);

        $first = app(ImportOhmLinksAction::class)($path, 'run-1', false, false);
        $primaryId = $entity->refresh()->primary_geo_ref_id;
        $second = app(ImportOhmLinksAction::class)($path, 'run-2', false, false);

        $this->assertSame($this->counters(['records' => 2, 'refs_updated' => 1, 'refs_created' => 2]), $first);
        $this->assertSame($this->counters(['records' => 2, 'skipped_existing' => 2]), $second);
        $this->assertSame(3, EntityGeoRef::query()->count());
        $this->assertSame($primaryId, $entity->refresh()->primary_geo_ref_id);
    }

    public function test_records_matching_nothing_are_counted_unmatched_and_not_kept(): void
    {
        Log::spy();
        Entity::factory()->create(['wikidata_id' => 'Q2277']);
        $this->ohmRef(Entity::factory()->create(), 'relation', '1880');

        $counters = $this->import([
            $this->record(['osm_id' => 2, 'wikidata_id' => 'Q999']),
            $this->record(['osm_type' => 'node', 'osm_id' => 1880, 'wikidata_id' => null]),
            $this->record(['osm_type' => 'way', 'osm_id' => 3, 'wikidata_id' => 'Q1000']),
        ]);

        $this->assertSame($this->counters(['records' => 3, 'unmatched' => 3]), $counters);
        $this->assertSame(1, EntityGeoRef::query()->count());
        Log::shouldHaveReceived('info')->once()->with('ohm-links: records loaded', ['records' => 3, 'kept' => 0]);
    }

    public function test_only_records_matching_a_ref_or_an_entity_qid_are_kept(): void
    {
        Log::spy();
        Entity::factory()->create(['wikidata_id' => 'Q2277']);
        $this->ohmRef(Entity::factory()->create(), 'relation', '1880', ['temporal_start_year' => 1, 'temporal_end_year' => 2]);

        $counters = $this->import([
            $this->record(['wikidata_id' => null]),                      // existing ref
            $this->record(['osm_type' => 'node', 'osm_id' => 7]),          // entity QID
            $this->record(['osm_id' => 2, 'wikidata_id' => 'Q999']),        // nothing
            $this->record(['osm_id' => 2, 'wikidata_id' => 'Q999']),        // duplicate line
            $this->record(['osm_type' => 'way', 'osm_id' => 3, 'wikidata_id' => null]), // nothing
        ]);

        $this->assertSame($this->counters(['records' => 4, 'refs_updated' => 1, 'refs_created' => 1, 'unmatched' => 2]), $counters);
        Log::shouldHaveReceived('info')->once()->with('ohm-links: records loaded', ['records' => 4, 'kept' => 2]);
    }

    public function test_chunk_1_over_three_qid_groups_creates_all_refs_with_the_unchunked_counters(): void
    {
        [$q1, $q2, $q3, $existing] = $this->seedThreeQidGroups();
        $path = $this->writeJsonl($this->threeQidGroupRecords());
        $expected = $this->counters(['records' => 5, 'refs_updated' => 1, 'refs_created' => 4]);

        $unchunked = app(ImportOhmLinksAction::class)($path, 'b', true, false, null, 1000);
        $this->assertSame($expected, $unchunked);

        $this->artisan('pipeline:import-ohm-links', ['path' => $path, '--chunk' => '1'])
            ->expectsTable(['Counter', 'Value'], $this->tableRows($expected))
            ->assertExitCode(0);

        $this->assertSame(-27, $existing->refresh()->temporal_start_year);
        $this->assertSame(GeoRefMatchRole::Primary, $this->onlyRef($q1, 'relation', '11')->match_role);
        $this->assertSame(GeoRefMatchRole::Primary, $this->onlyRef($q2, 'relation', '21')->match_role);
        $this->assertSame(GeoRefMatchRole::Candidate, $this->onlyRef($q2, 'node', '22')->match_role);
        $this->assertSame(GeoRefMatchRole::Primary, $this->onlyRef($q3, 'relation', '31')->match_role);
        $this->assertSame(5, EntityGeoRef::query()->count());
    }

    public function test_dry_run_with_chunk_1_writes_nothing(): void
    {
        [$q1, $q2, $q3, $existing] = $this->seedThreeQidGroups();
        $path = $this->writeJsonl($this->threeQidGroupRecords());

        $this->artisan('pipeline:import-ohm-links', ['path' => $path, '--chunk' => '1', '--dry-run' => true])
            ->expectsTable(['Counter', 'Value'], $this->tableRows($this->counters(['records' => 5, 'refs_updated' => 1, 'refs_created' => 4])))
            ->assertExitCode(0);

        $this->assertSame(1, EntityGeoRef::query()->count());
        $existing->refresh();
        $this->assertSame([null, null, null], [$existing->temporal_start_year, $existing->temporal_start, $existing->external_tags]);
        foreach ([$q1, $q2, $q3] as $entity) {
            $this->assertNull($entity->refresh()->primary_geo_ref_id);
        }
    }

    public function test_a_crash_mid_way_keeps_committed_chunks_and_a_rerun_completes_them(): void
    {
        [$q1, $q2, $q3, $existing] = $this->seedThreeQidGroups();
        $path = $this->writeJsonl($this->threeQidGroupRecords());
        $this->app->instance(CreateEntityGeoRefAction::class, new class extends CreateEntityGeoRefAction
        {
            private int $calls = 0;

            public function __invoke(Entity $entity, array $attributes): EntityGeoRef
            {
                if (++$this->calls === 2) {
                    throw new RuntimeException('simulated crash');
                }

                return parent::__invoke($entity, $attributes);
            }
        });

        try {
            app(ImportOhmLinksAction::class)($path, 'b', false, false, null, 1);
            $this->fail('the simulated crash should propagate');
        } catch (RuntimeException $e) {
            $this->assertSame('simulated crash', $e->getMessage());
        }

        // The rule-2 chunk and the Q1 chunk committed; the Q2 chunk rolled back whole; Q3 never ran.
        $this->assertSame(-27, $existing->refresh()->temporal_start_year);
        $this->assertSame($this->onlyRef($q1, 'relation', '11')->geo_ref_id, $q1->refresh()->primary_geo_ref_id);
        $this->assertSame(0, EntityGeoRef::query()->whereIn('entity_id', [$q2->entity_id, $q3->entity_id])->count());
        $this->assertNull($q2->refresh()->primary_geo_ref_id);

        $this->app->forgetInstance(CreateEntityGeoRefAction::class);
        $rerun = app(ImportOhmLinksAction::class)($path, 'b', false, false, null, 1);

        $this->assertSame($this->counters(['records' => 5, 'refs_created' => 3, 'skipped_existing' => 1]), $rerun);
        $this->assertSame(5, EntityGeoRef::query()->count());
    }

    public function test_chunk_must_be_a_positive_integer(): void
    {
        $path = $this->writeJsonl([$this->record()]);

        $this->artisan('pipeline:import-ohm-links', ['path' => $path, '--chunk' => '0'])->assertExitCode(1);
    }

    /**
     * Entities for Q1, Q2 and Q3 (no refs) and an unrelated OHM ref relation/99 with empty fields.
     *
     * @return array{0: Entity, 1: Entity, 2: Entity, 3: EntityGeoRef}
     */
    private function seedThreeQidGroups(): array
    {
        return [
            Entity::factory()->create(['wikidata_id' => 'Q1']),
            Entity::factory()->create(['wikidata_id' => 'Q2']),
            Entity::factory()->create(['wikidata_id' => 'Q3']),
            $this->ohmRef(Entity::factory()->create(), 'relation', '99', [
                'temporal_start_year' => null,
                'temporal_end_year' => null,
                'external_tags' => null,
            ]),
        ];
    }

    /** @return list<array<string, mixed>> */
    private function threeQidGroupRecords(): array
    {
        return [
            $this->record(['osm_id' => 99, 'wikidata_id' => null]),
            $this->record(['osm_id' => 11, 'wikidata_id' => 'Q1']),
            $this->record(['osm_id' => 21, 'wikidata_id' => 'Q2']),
            $this->record(['osm_type' => 'node', 'osm_id' => 22, 'wikidata_id' => 'Q2']),
            $this->record(['osm_id' => 31, 'wikidata_id' => 'Q3']),
        ];
    }

    public function test_malformed_lines_are_counted_and_skipped(): void
    {
        $path = $this->writeJsonl([$this->record(['wikidata_id' => null])]);
        file_put_contents($path, "\nnot json\n".json_encode(['osm_type' => 'qid', 'osm_id' => 1])."\n", FILE_APPEND);

        $counters = app(ImportOhmLinksAction::class)($path, 'batch', false, false);

        $this->assertSame($this->counters(['unmatched' => 1, 'malformed' => 2]), $counters);
    }

    public function test_missing_file_fails(): void
    {
        $this->artisan('pipeline:import-ohm-links', ['path' => '/nonexistent/ohm_links.jsonl'])
            ->assertExitCode(1);
    }

    /**
     * @param  array<string, mixed>  $overrides
     * @return array<string, mixed>
     */
    private function record(array $overrides = []): array
    {
        return [
            'osm_type' => 'relation',
            'osm_id' => 1880,
            'wikidata_id' => 'Q2277',
            'name' => 'Imperium Romanum',
            'name_en' => 'Roman Empire',
            'admin_level' => 2,
            'place' => null,
            'start_date' => '-0027-01-16',
            'end_date' => '0476-09-04',
            'tags' => self::TAGS,
            ...$overrides,
        ];
    }

    /**
     * @param  array<string, int>  $overrides
     * @return array<string, int>
     */
    private function counters(array $overrides = []): array
    {
        return [
            'records' => 1,
            'refs_updated' => 0,
            'refs_created' => 0,
            'skipped_existing' => 0,
            'invalid_years' => 0,
            'qid_duplicates' => 0,
            'unmatched' => 0,
            'malformed' => 0,
            ...$overrides,
        ];
    }

    /**
     * @param  array<string, int>  $counters
     * @return list<array{0: string, 1: int}>
     */
    private function tableRows(array $counters): array
    {
        return array_map(fn (string $name, int $value): array => [$name, $value], array_keys($counters), $counters);
    }

    /**
     * @param  list<array<string, mixed>>  $records
     * @return array<string, int>
     */
    private function import(array $records): array
    {
        return app(ImportOhmLinksAction::class)($this->writeJsonl($records), 'test-batch', false, false);
    }

    /**
     * @param  list<array<string, mixed>>  $records
     */
    private function writeJsonl(array $records): string
    {
        $dir = sys_get_temp_dir().'/'.uniqid('ohm-links-run-');
        mkdir($dir);
        $path = $dir.'/ohm_links.jsonl';
        file_put_contents($path, implode("\n", array_map(fn (array $r): string => json_encode($r), $records))."\n");

        $this->beforeApplicationDestroyed(function () use ($dir, $path): void {
            @unlink($path);
            @rmdir($dir);
        });

        return $path;
    }

    /**
     * @param  array<string, mixed>  $attributes
     */
    private function ohmRef(Entity $entity, string $type, string $externalId, array $attributes = []): EntityGeoRef
    {
        return EntityGeoRef::factory()->forEntity($entity)->create([
            'provider' => GeoRefProvider::Ohm->value,
            'external_type' => $type,
            'external_id' => $externalId,
            ...$attributes,
        ]);
    }

    private function onlyRef(Entity $entity, string $type, string $externalId): EntityGeoRef
    {
        return EntityGeoRef::query()
            ->where('entity_id', $entity->entity_id)
            ->where('provider', GeoRefProvider::Ohm->value)
            ->where('external_type', $type)
            ->where('external_id', $externalId)
            ->sole();
    }
}
