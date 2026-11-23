<?php

declare(strict_types=1);

namespace Tests\Feature\Tags;

use App\Actions\Tag\DeriveTagsAction;
use App\Actions\Tag\ResolveTagsAction;
use App\Actions\Tag\SyncTagsAction;
use App\Enums\EntityType;
use App\Enums\TagFacet;
use App\Enums\TagSource;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use App\Models\Tag;
use Database\Seeders\TagSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class TagDerivationTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->seed(TagSeeder::class);
    }

    /** @return list<string> */
    private function tagsOf(Chronicle|Entity $model, ?TagSource $source = null): array
    {
        [$table, $key] = $model instanceof Chronicle ? ['chronicle_tags', 'chronicle_id'] : ['entity_tags', 'entity_id'];

        return DB::table($table)
            ->where($key, $model->getKey())
            ->when($source, fn ($q) => $q->where('source', $source->value))
            ->orderBy('tag')
            ->pluck('tag')
            ->all();
    }

    private function putInChronicle(Entity $entity, Chronicle $chronicle): void
    {
        $entry = ChronicleEntry::create([
            'entry_id' => (string) Str::uuid(),
            'chronicle_id' => $chronicle->chronicle_id,
            'sequence_order' => ChronicleEntry::where('chronicle_id', $chronicle->chronicle_id)->count(),
            'narrative_text' => 'Step',
        ]);
        $entry->secondaryEntities()->attach($entity->entity_id, ['role' => 'participant', 'sequence_in_entry' => 0]);
    }

    /** Give the entity a primary map point. */
    private function place(Entity $entity, float $lng, float $lat): void
    {
        DB::table('entity_locations')->where('entity_id', $entity->entity_id)->delete();
        DB::statement(
            "INSERT INTO entity_locations (location_id, entity_id, geom, location_method, location_confidence, is_primary, created_at, updated_at)
             VALUES (gen_random_uuid(), ?, ST_SetSRID(ST_MakePoint(?, ?), 4326), 'human_assigned'::location_resolution_method, 'high'::confidence_level, true, NOW(), NOW())",
            [$entity->entity_id, $lng, $lat],
        );
    }

    /** @return list<string> the entity's region tags */
    private function regionsOf(Entity $entity): array
    {
        return DB::table('entity_tags')
            ->join('tags', 'tags.slug', '=', 'entity_tags.tag')
            ->where('entity_tags.entity_id', $entity->entity_id)
            ->where('tags.facet', TagFacet::Region->value)
            ->orderBy('entity_tags.tag')
            ->pluck('entity_tags.tag')
            ->all();
    }

    private function chronicleTagged(array $tags, ?int $start = null, ?int $end = null): Chronicle
    {
        $chronicle = Chronicle::factory()->create(['start_year' => $start, 'end_year' => $end]);
        app(SyncTagsAction::class)($chronicle, $tags, TagSource::Curated);

        return $chronicle;
    }

    public function test_vocabulary_seeds_facets_and_parents(): void
    {
        $china = Tag::findOrFail('china');

        $this->assertSame(TagFacet::Region, $china->facet);
        $this->assertSame('east-asia', $china->parent_slug);
        $this->assertSame(-3000, Tag::findOrFail('ancient')->start_year);
        $this->assertSame(1, Tag::where('facet', 'type')->where('slug', 'polity')->count());
    }

    public function test_resolve_matches_slugs_and_names_and_creates_topics(): void
    {
        $slugs = app(ResolveTagsAction::class)(['bronze-age', 'Mesoamerica', '  Vikings ', '', 42]);

        $this->assertSame(['bronze-age', 'mesoamerica', 'vikings'], $slugs);
        $this->assertSame(TagFacet::Topic, Tag::findOrFail('vikings')->facet);
        $this->assertSame('Vikings', Tag::findOrFail('vikings')->name);
    }

    public function test_sync_stores_ancestors(): void
    {
        $chronicle = Chronicle::factory()->create();

        app(SyncTagsAction::class)($chronicle, ['china', 'neolithic'], TagSource::Curated);

        $this->assertSame(['asia', 'china', 'east-asia', 'neolithic', 'prehistory'], $this->tagsOf($chronicle));
    }

    public function test_manual_chronicle_tags_replace_curated_and_curated_never_replaces_manual(): void
    {
        $chronicle = $this->chronicleTagged(['egypt', 'polity']);

        app(SyncTagsAction::class)($chronicle, ['nubia'], TagSource::Manual);
        $this->assertSame(['africa', 'nubia'], $this->tagsOf($chronicle));

        app(SyncTagsAction::class)($chronicle, ['egypt'], TagSource::Curated);
        $this->assertSame(['africa', 'nubia'], $this->tagsOf($chronicle, TagSource::Manual));
    }

    public function test_entity_manual_tags_leave_derived_tags_alone(): void
    {
        $entity = Entity::factory()->create();
        DB::table('entity_tags')->insert(['entity_id' => $entity->entity_id, 'tag' => 'war', 'source' => 'derived']);

        app(SyncTagsAction::class)($entity, ['Vikings'], TagSource::Manual);

        $this->assertSame(['vikings', 'war'], $this->tagsOf($entity));
    }

    public function test_chronicle_era_is_derived_from_years_only_when_untagged_by_era(): void
    {
        $dated = Chronicle::factory()->create(['start_year' => 1350, 'end_year' => 1700]);
        $curated = $this->chronicleTagged(['early-modern'], 1350, 1700);

        app(DeriveTagsAction::class)->chronicles();

        $this->assertSame(['early-modern', 'medieval'], $this->tagsOf($dated, TagSource::Derived));
        $this->assertSame([], $this->tagsOf($curated, TagSource::Derived));
    }

    public function test_entity_era_comes_from_its_dates_and_origin_types_use_start_only(): void
    {
        $empire = Entity::factory()->withTemporalRange('-0027', '1453')->ofType(EntityType::PoliticalEntity)->create();
        $city = Entity::factory()->withTemporalRange('-0753', '2000')->ofType(EntityType::City)->create();

        app(DeriveTagsAction::class)();

        $this->assertSame(['classical', 'empires-states', 'medieval'], $this->tagsOf($empire));
        $this->assertSame(['ancient'], $this->tagsOf($city));
    }

    public function test_entity_inherits_regions_but_not_from_thematic_chronicles(): void
    {
        $entity = Entity::factory()->withTemporalRange('1100', '1150')->ofType(EntityType::Person)->create();
        $this->putInChronicle($entity, $this->chronicleTagged(['caucasus', 'regional']));
        $this->putInChronicle($entity, $this->chronicleTagged(['global', 'indian-ocean', 'thematic']));

        app(DeriveTagsAction::class)();

        $this->assertSame(['asia', 'caucasus', 'medieval'], $this->tagsOf($entity));
    }

    public function test_hub_entities_keep_only_their_dominant_regions(): void
    {
        $hub = Entity::factory()->withTemporalRange('-0100', '-0044')->ofType(EntityType::Person)->create();
        foreach (range(1, 3) as $i) {
            $this->putInChronicle($hub, $this->chronicleTagged(['italy', 'regional']));
        }
        $this->putInChronicle($hub, $this->chronicleTagged(['egypt', 'regional']));

        app(DeriveTagsAction::class)();

        // europe/italy: 3 of 4 chronicles; africa/egypt: 1 of 4 (< half the top count).
        $this->assertSame(['classical', 'europe', 'italy'], $this->tagsOf($hub));
    }

    public function test_a_placed_battle_keeps_only_the_chronicle_regions_its_point_is_in(): void
    {
        $worldWarOne = $this->chronicleTagged(['europe', 'middle-east', 'conflict']);
        $ypres = Entity::factory()->ofType(EntityType::EventBattle)->create(['name' => 'First Battle of Ypres']);
        $this->place($ypres, 2.89, 50.85);
        $gallipoli = Entity::factory()->ofType(EntityType::EventBattle)->create(['name' => 'Gallipoli campaign']);
        $this->place($gallipoli, 26.4, 40.2);
        $this->putInChronicle($ypres, $worldWarOne);
        $this->putInChronicle($gallipoli, $worldWarOne);

        app(DeriveTagsAction::class)();

        $this->assertSame(['europe'], $this->regionsOf($ypres));
        // Anatolia's footprint reaches the Dardanelles, so the Middle East (and Asia) stay.
        $this->assertSame(['asia', 'europe', 'middle-east'], $this->regionsOf($gallipoli));
    }

    public function test_entities_without_a_point_or_of_a_spread_out_type_keep_every_chronicle_region(): void
    {
        $chronicle = $this->chronicleTagged(['europe', 'middle-east', 'conflict']);
        $unplaced = Entity::factory()->ofType(EntityType::EventBattle)->create();
        $person = Entity::factory()->ofType(EntityType::Person)->create(); // a point is a birthplace
        $this->place($person, 2.89, 50.85);
        $war = Entity::factory()->ofType(EntityType::EventWar)->create();
        $this->place($war, 2.89, 50.85);
        foreach ([$unplaced, $person, $war] as $entity) {
            $this->putInChronicle($entity, $chronicle);
        }

        app(DeriveTagsAction::class)();

        foreach ([$unplaced, $person, $war] as $entity) {
            $this->assertSame(['asia', 'europe', 'middle-east'], $this->regionsOf($entity));
        }
    }

    public function test_a_shape_or_a_second_location_counts_as_a_place(): void
    {
        $chronicle = $this->chronicleTagged(['egypt', 'levant', 'regional']);
        $city = Entity::factory()->ofType(EntityType::City)->create();
        DB::statement(
            "INSERT INTO geometry_periods (entity_id, period_type, start_year, territory_geom, provenance_mode)
             VALUES (?, 'territory', -1500, ST_SetSRID(ST_MakeEnvelope(35.1, 32.5, 35.3, 32.7), 4326), 'manual')",
            [$city->entity_id],
        );
        $fort = Entity::factory()->ofType(EntityType::InfrastructureMonument)->create();
        $this->place($fort, 31.2, 30.0); // Cairo
        DB::statement(
            'INSERT INTO entity_locations (location_id, entity_id, geom, is_primary, created_at, updated_at)
             VALUES (gen_random_uuid(), ?, ST_SetSRID(ST_MakePoint(35.2, 31.8), 4326), false, NOW(), NOW())',
            [$fort->entity_id],
        );
        $this->putInChronicle($city, $chronicle);
        $this->putInChronicle($fort, $chronicle);

        app(DeriveTagsAction::class)();

        $this->assertSame(['asia', 'levant', 'middle-east'], $this->regionsOf($city));
        $this->assertSame(['africa', 'asia', 'egypt', 'levant', 'middle-east'], $this->regionsOf($fort));
    }

    public function test_a_region_far_from_the_point_does_not_count_in_the_weighing(): void
    {
        $rome = Entity::factory()->ofType(EntityType::City)->create();
        $this->place($rome, 12.48, 41.89);
        foreach (range(1, 5) as $i) {
            $this->putInChronicle($rome, $this->chronicleTagged(['egypt', 'regional']));
        }
        foreach (range(1, 2) as $i) {
            $this->putInChronicle($rome, $this->chronicleTagged(['italy', 'regional']));
        }

        app(DeriveTagsAction::class)();

        // Unchecked, Egypt (5 of 7 chronicles) would outweigh Italy (2 of 7).
        $this->assertSame(['europe', 'italy'], $this->regionsOf($rome));
    }

    public function test_manual_region_tags_are_kept_whatever_the_point(): void
    {
        $battle = Entity::factory()->ofType(EntityType::EventBattle)->create();
        $this->place($battle, 2.89, 50.85);
        app(SyncTagsAction::class)($battle, ['japan'], TagSource::Manual);
        $this->putInChronicle($battle, $this->chronicleTagged(['china', 'regional']));

        app(DeriveTagsAction::class)();

        // China is dropped; the manual Japan (and its ancestors) are not.
        $this->assertSame(['asia', 'east-asia', 'japan'], $this->tagsOf($battle, TagSource::Manual));
        $this->assertSame(['asia', 'east-asia', 'japan'], $this->regionsOf($battle));
    }

    public function test_sub_eras_are_inherited_only_inside_their_window_and_bring_their_parent(): void
    {
        $bronzeChronicle = $this->chronicleTagged(['bronze-age', 'iron-age', 'italy', 'regional']);
        $rome = Entity::factory()->withTemporalRange('-0753', '0000')->ofType(EntityType::City)->create();
        $undated = Entity::factory()->ofType(EntityType::Person)->create();
        $this->putInChronicle($rome, $bronzeChronicle);
        $this->putInChronicle($undated, $bronzeChronicle);

        app(DeriveTagsAction::class)();

        $this->assertContains('iron-age', $this->tagsOf($rome));
        $this->assertNotContains('bronze-age', $this->tagsOf($rome));
        // No dates of its own: era and sub-eras all come from the chronicle.
        $this->assertSame(['ancient', 'bronze-age', 'europe', 'iron-age', 'italy'], $this->tagsOf($undated));
    }

    public function test_a_massacre_typed_as_a_battle_is_tagged_from_its_wikidata_class(): void
    {
        $massacre = Entity::factory()->ofType(EntityType::EventBattle)->create(['attributes' => ['_p31' => ['Q3199915']]]);
        $battle = Entity::factory()->ofType(EntityType::EventBattle)->create(['attributes' => ['_p31' => ['Q178561']]]);
        $curated = Entity::factory()->ofType(EntityType::EventBattle)->create(['attributes' => ['_p31' => 'Q3199915']]);

        app(DeriveTagsAction::class)();

        $this->assertSame(['massacres', 'war'], $this->tagsOf($massacre));
        $this->assertSame(['war'], $this->tagsOf($battle));
        $this->assertSame(['war'], $this->tagsOf($curated)); // not an array: ignored
    }

    public function test_derive_replaces_previous_derived_tags_and_keeps_manual_ones(): void
    {
        $entity = Entity::factory()->ofType(EntityType::EventBattle)->create();
        DB::table('entity_tags')->insert(['entity_id' => $entity->entity_id, 'tag' => 'religion', 'source' => 'derived']);
        app(SyncTagsAction::class)($entity, ['Crusades'], TagSource::Manual);

        app(DeriveTagsAction::class)();

        $this->assertSame(['crusades', 'war'], $this->tagsOf($entity));
    }

    public function test_tags_sync_command_applies_curated_file_and_skips_admin_tagged_chronicles(): void
    {
        $curated = json_decode((string) file_get_contents(database_path('data/tags/chronicles.json')), true)['chronicles'];
        [$slugA, $slugB] = array_slice(array_keys($curated), 0, 2);
        $a = Chronicle::factory()->create(['slug' => $slugA]);
        $b = Chronicle::factory()->create(['slug' => $slugB]);
        app(SyncTagsAction::class)($b, ['polar'], TagSource::Manual);

        $this->artisan('tags:sync')->assertExitCode(0);

        $this->assertEqualsCanonicalizing(
            ResolveTagsAction::withAncestors($curated[$slugA]),
            $this->tagsOf($a, TagSource::Curated),
        );
        $this->assertSame(['polar'], $this->tagsOf($b));
    }

    public function test_every_curated_tag_is_in_the_vocabulary_with_exactly_one_type(): void
    {
        $vocabulary = Tag::pluck('facet', 'slug');
        $curated = json_decode((string) file_get_contents(database_path('data/tags/chronicles.json')), true)['chronicles'];

        foreach ($curated as $slug => $tags) {
            foreach ($tags as $tag) {
                $this->assertTrue($vocabulary->has($tag), "{$slug}: unknown tag {$tag}");
            }
            $types = array_filter($tags, fn (string $t): bool => $vocabulary[$t] === TagFacet::Type);
            $this->assertCount(1, $types, "{$slug}: needs exactly one type tag");
        }
    }
}
