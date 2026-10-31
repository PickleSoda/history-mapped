<?php

declare(strict_types=1);

namespace Tests\Feature\Console;

use App\Actions\EntityGeoRef\ImportOhmLinksAction;
use App\Enums\GeoRefExternalType;
use App\Enums\GeoRefMatchRole;
use App\Enums\GeoRefProvider;
use App\Enums\GeoRefRetrievalMethod;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use Illuminate\Foundation\Testing\RefreshDatabase;
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

    public function test_e_dry_run_rolls_back_and_reports_the_counters(): void
    {
        Entity::factory()->create(['wikidata_id' => 'Q2277']);
        $path = $this->writeJsonl([$this->record()]);

        $this->artisan('pipeline:import-ohm-links', ['path' => $path, '--dry-run' => true])
            ->expectsTable(['Counter', 'Value'], $this->tableRows($this->counters(['refs_created' => 1])))
            ->assertExitCode(0);

        $this->assertSame(0, EntityGeoRef::query()->count());
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
        ]);
        $path = $this->writeJsonl([$this->record()]);

        $this->artisan('pipeline:import-ohm-links', ['path' => $path])->assertExitCode(0);

        $ref->refresh();
        $this->assertSame(100, $ref->temporal_start_year);
        $this->assertSame(200, $ref->temporal_end_year);

        $this->artisan('pipeline:import-ohm-links', ['path' => $path, '--overwrite-years' => true])
            ->expectsTable(['Counter', 'Value'], $this->tableRows($this->counters(['refs_updated' => 1])))
            ->assertExitCode(0);

        $ref->refresh();
        $this->assertSame(-27, $ref->temporal_start_year);
        $this->assertSame(476, $ref->temporal_end_year);
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
