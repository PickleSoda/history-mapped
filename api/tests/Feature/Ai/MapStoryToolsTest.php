<?php

declare(strict_types=1);

namespace Tests\Feature\Ai;

use App\Ai\ProposalApplier;
use App\Ai\Tools\CreateMapStory;
use App\Ai\Tools\GetMapStory;
use App\Ai\Tools\ToolArgumentException;
use App\Ai\Tools\UpdateMapStory;
use App\Ai\Tools\ValidateMapStory;
use App\Enums\EntityType;
use App\Models\Ai\ProposedChange;
use App\Models\Entity;
use App\Models\MapStory;
use App\Models\User;
use App\Support\MapStory\MapStoryFile;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\File;
use Laravel\Ai\Tools\Request;
use Symfony\Component\HttpKernel\Exception\UnprocessableEntityHttpException;
use Tests\Feature\MapStory\MapStoryFixture;
use Tests\TestCase;

/** get_map_story, validate_map_story, create_map_story and update_map_story: proposals like every other edit. */
class MapStoryToolsTest extends TestCase
{
    use RefreshDatabase;

    private string $dir;

    private Entity $battle;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();
        $this->dir = MapStoryFixture::directory();
        $this->battle = Entity::factory()->ofType(EntityType::EventBattle)->create(['name' => 'Battle of Testfield', 'wikidata_id' => 'Q179591']);
        $this->user = User::factory()->create();
    }

    protected function tearDown(): void
    {
        File::deleteDirectory($this->dir);
        parent::tearDown();
    }

    private function story(): MapStory
    {
        $doc = MapStoryFixture::v2Document();
        file_put_contents($this->dir.'/'.$doc['slug'].'.json', MapStoryFile::encode(MapStoryFile::fromArray($doc)));
        $this->artisan('map-stories:sync', ['--path' => $this->dir])->assertSuccessful();

        return MapStory::query()->sole();
    }

    private function tool(string $tool, array $args): array
    {
        $tool = app($tool)->withContext(['user_id' => $this->user->id, 'context_type' => 'entity', 'context_id' => $this->battle->entity_id]);

        return json_decode((string) $tool->handle(new Request($args)), true);
    }

    public function test_get_map_story_reads_by_part_with_pointers(): void
    {
        $this->story();

        $overview = $this->tool(GetMapStory::class, ['entity_id' => $this->battle->entity_id]);
        $this->assertSame('battle-of-testfield', $overview['slug']);
        $this->assertSame('terrain', $overview['features_key']);
        $this->assertSame(['pointer' => '/steps/1', 'id' => 'clash', 'title' => 'The clash'], $overview['steps'][1]);
        $this->assertArrayNotHasKey('steps', $overview['document']);

        $units = $this->tool(GetMapStory::class, ['slug' => 'battle-of-testfield', 'part' => 'units']);
        $this->assertSame('/units/0', $units['units'][0]['pointer']);
        $this->assertArrayNotHasKey('entity_id', $units['units'][0]);

        $step = $this->tool(GetMapStory::class, ['slug' => 'battle-of-testfield', 'part' => 'step:clash']);
        $this->assertSame('/steps/1', $step['pointer']);
        $this->assertSame('The wing rejoins the line', $step['step']['beats'][0]['label']);

        $full = $this->tool(GetMapStory::class, ['slug' => 'battle-of-testfield', 'part' => 'full']);
        $this->assertSame('Battle of Testfield', $full['document']['title']);

        $this->assertStringContainsString("No map story with slug 'nope'", $this->tool(GetMapStory::class, ['slug' => 'nope'])['error']);
    }

    public function test_full_is_capped(): void
    {
        $story = $this->story();
        $doc = MapStoryFile::authored($story->document);
        $doc->uncertainty = str_repeat('Long. ', 11000);
        MapStory::query()->whereKey($story->story_id)->update(['document' => json_encode($doc)]);

        $this->assertStringContainsString('use part=overview', strtolower($this->tool(GetMapStory::class, ['slug' => 'battle-of-testfield', 'part' => 'full'])['error']));
    }

    public function test_validate_map_story_checks_the_stored_or_a_given_document(): void
    {
        $story = $this->story();

        $stored = $this->tool(ValidateMapStory::class, ['slug' => 'battle-of-testfield']);
        $this->assertTrue($stored['ok']);

        $doc = MapStoryFile::toArray(MapStoryFile::authored($story->document));
        $doc['steps'][0]['positions']['red-foot']['shape'] = 'blob';
        $given = $this->tool(ValidateMapStory::class, ['slug' => 'battle-of-testfield', 'document' => $doc]);
        $this->assertFalse($given['ok']);
        $this->assertStringContainsString('shape', $given['errors'][0]);
    }

    public function test_update_map_story_stages_a_proposal_that_applies_as_an_ai_revision(): void
    {
        $story = $this->story();

        $staged = $this->tool(UpdateMapStory::class, [
            'slug' => 'battle-of-testfield',
            'ops' => [
                ['op' => 'replace', 'path' => '/steps/1/narrative', 'value' => 'The blue horse charges the red foot at the ford.'],
                ['op' => 'replace', 'path' => '/steps/1/positions/red-wing/at', 'value' => [16.136, 41.301]],
            ],
            'note' => 'sharper narrative',
        ]);

        $this->assertArrayHasKey('proposal_id', $staged);
        $part = $staged['parts'][0];
        $this->assertSame('update_map_story', $part['tool']);
        $this->assertSame('They fight.', $part['human_diff']['diff']['0. replace /steps/1/narrative']['from']);
        $this->assertIsArray($part['human_diff']['warnings']);
        $this->assertSame('They fight.', $story->fresh()->document->steps[1]->narrative, 'nothing is written until applied');

        $this->actingAs($this->user);
        app(ProposalApplier::class)->applyPart(ProposedChange::query()->sole()->parts()->sole());

        $story->refresh();
        $this->assertSame('The blue horse charges the red foot at the ford.', $story->document->steps[1]->narrative);
        $this->assertSame([16.136, 41.301], $story->document->steps[1]->positions->{'red-wing'}->at);
        $revision = $story->revisions()->first();
        $this->assertSame(['ai', 'sharper narrative', $this->user->id], [$revision->source, $revision->note, $revision->user_id]);
        $this->assertTrue($story->isEdited());
    }

    public function test_update_map_story_rejects_the_whole_patch_and_stages_nothing(): void
    {
        $story = $this->story();

        $bad = $this->tool(UpdateMapStory::class, ['slug' => 'battle-of-testfield', 'ops' => [
            ['op' => 'replace', 'path' => '/title', 'value' => 'Fine'],
            ['op' => 'replace', 'path' => '/units/0/kind', 'value' => 'dragons'],
        ]]);
        $this->assertStringContainsString('Patch rejected — nothing staged', $bad['error']);
        $this->assertStringContainsString("'dragons'", $bad['error']);

        $missing = $this->tool(UpdateMapStory::class, ['slug' => 'battle-of-testfield', 'ops' => [
            ['op' => 'remove', 'path' => '/steps/7'],
        ]]);
        $this->assertStringContainsString('index 7 is out of range', $missing['error']);

        $this->assertSame(0, ProposedChange::query()->count());
        $this->assertSame('Battle of Testfield', $story->fresh()->title);
    }

    public function test_an_update_that_no_longer_applies_is_refused_at_apply_time(): void
    {
        $story = $this->story();
        $parts = app(UpdateMapStory::class)->buildParts(['slug' => 'battle-of-testfield', 'ops' => [
            ['op' => 'test', 'path' => '/title', 'value' => 'Battle of Testfield'],
            ['op' => 'replace', 'path' => '/outcome', 'value' => 'Blue wins.'],
        ]]);
        MapStory::query()->whereKey($story->story_id)->update(['document' => json_encode(['title' => 'changed meanwhile'] + (array) MapStoryFile::toArray($story->document))]);

        $this->expectException(UnprocessableEntityHttpException::class);
        app(UpdateMapStory::class)->applyPart($parts[0]['payload'], ['user_id' => (string) $this->user->id]);
    }

    public function test_create_map_story_stages_a_skeleton_and_applies_it(): void
    {
        $staged = $this->tool(CreateMapStory::class, [
            'entity_id' => $this->battle->entity_id, 'kind' => 'battle', 'title' => 'Battle of Testfield', 'year' => -216,
            'sides' => [['id' => 'rome', 'name' => 'Rome'], ['id' => 'carthage', 'name' => 'Carthage', 'color' => '#6d28d9']],
        ]);
        $this->assertSame('battle-of-testfield', $staged['parts'][0]['human_diff']['diff']['slug']['to']);
        $this->assertSame(0, MapStory::query()->count());

        $this->actingAs($this->user);
        $applied = app(ProposalApplier::class)->applyPart(ProposedChange::query()->sole()->parts()->sole());

        $story = MapStory::query()->sole();
        $this->assertSame($story->story_id, $applied->result_id);
        $this->assertSame($this->battle->entity_id, $story->entity_id);
        $this->assertSame(['Rome', 'Carthage'], array_column($story->document->sides, 'name'));
        $this->assertSame('#6d28d9', $story->document->sides[1]->color);
        $this->assertSame(['rome-main', 'carthage-main'], array_column($story->document->units, 'id'));
        $this->assertSame('ai', $story->revisions()->sole()->source);
    }

    public function test_create_map_story_refuses_an_invalid_skeleton(): void
    {
        $this->expectException(ToolArgumentException::class);
        $this->expectExceptionMessage('nothing staged');

        app(CreateMapStory::class)->buildParts([
            'entity_id' => $this->battle->entity_id, 'kind' => 'battle', 'title' => 'One-sided', 'year' => -216,
            'sides' => [['id' => 'rome', 'name' => 'Rome']],
        ]);
    }
}
