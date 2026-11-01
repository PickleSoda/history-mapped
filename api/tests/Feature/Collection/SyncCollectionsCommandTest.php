<?php

declare(strict_types=1);

namespace Tests\Feature\Collection;

use App\Enums\CollectionStatus;
use App\Models\Collection;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

/** `collections:sync`: resources/collections/*.json → `collections`. */
class SyncCollectionsCommandTest extends TestCase
{
    use RefreshDatabase;

    private string $dir;

    protected function setUp(): void
    {
        parent::setUp();
        $this->dir = storage_path('framework/testing/collections-'.bin2hex(random_bytes(4)));
        File::ensureDirectoryExists($this->dir);
    }

    protected function tearDown(): void
    {
        File::deleteDirectory($this->dir);
        parent::tearDown();
    }

    /** @param  array<string, mixed>  $data */
    private function write(array $data, ?string $file = null): void
    {
        File::put($this->dir.'/'.($file ?? $data['slug']).'.json', json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
    }

    /** @return array{0: int, 1: string} exit code and output */
    private function sync(?string $path = null): array
    {
        $code = Artisan::call('collections:sync', $path === '' ? [] : ['--path' => $path ?? $this->dir]);

        return [$code, Artisan::output()];
    }

    /** @return array<string, mixed> */
    private function set(array $overrides = []): array
    {
        return [
            'slug' => 'the-roman-world',
            'title' => 'The Roman World',
            'subtitle' => 'From republic to empire',
            'description' => "Rome's rise.\n\nAnd its fall.",
            'cover_qid' => 'Q2277',
            'sort_order' => 2,
            'items' => [
                ['kind' => 'entity', 'ref' => 'Q2277', 'note' => 'The empire itself.'],
                ['kind' => 'chronicle', 'ref' => 'punic-wars'],
                ['kind' => 'story', 'ref' => 'battle-of-cannae', 'note' => ''],
                ['kind' => 'tag', 'ref' => 'classical'],
            ],
            ...$overrides,
        ];
    }

    public function test_creates_a_collection_and_resolves_its_cover(): void
    {
        $rome = Entity::factory()->create(['name' => 'Roman Empire', 'wikidata_id' => 'Q2277']);
        $this->write($this->set());

        [$code, $output] = $this->sync();

        $this->assertSame(0, $code);
        $this->assertMatchesRegularExpression('/the-roman-world \.+ created/', $output);
        $row = Collection::query()->sole();
        $this->assertSame(['the-roman-world', 'The Roman World', 'From republic to empire', 2], [$row->slug, $row->title, $row->subtitle, $row->sort_order]);
        $this->assertSame("Rome's rise.\n\nAnd its fall.", $row->description);
        $this->assertSame(CollectionStatus::Published, $row->status);
        $this->assertSame($rome->entity_id, $row->cover_entity_id);
        $this->assertEquals([
            ['kind' => 'entity', 'ref' => 'Q2277', 'note' => 'The empire itself.'],
            ['kind' => 'chronicle', 'ref' => 'punic-wars'],
            ['kind' => 'story', 'ref' => 'battle-of-cannae'],
            ['kind' => 'tag', 'ref' => 'classical'],
        ], $row->items, 'items keep their order; an empty note is dropped');
    }

    public function test_updates_changed_files_skips_unchanged_ones_and_deletes_nothing(): void
    {
        $this->write($this->set());
        $this->write($this->set(['slug' => 'silk-roads', 'title' => 'The Silk Roads', 'cover_qid' => null]));
        $this->assertSame(0, $this->sync()[0]);
        $id = Collection::query()->where('slug', 'the-roman-world')->value('collection_id');

        [$code, $output] = $this->sync();
        $this->assertSame(0, $code);
        $this->assertMatchesRegularExpression('/silk-roads \.+ unchanged/', $output);
        $this->assertMatchesRegularExpression('/the-roman-world \.+ unchanged/', $output);

        $this->write($this->set(['title' => 'Rome', 'items' => [['kind' => 'tag', 'ref' => 'europe']]]));
        File::delete($this->dir.'/silk-roads.json');

        [$code, $output] = $this->sync();
        $this->assertSame(0, $code);
        $this->assertMatchesRegularExpression('/the-roman-world \.+ updated/', $output);

        $row = Collection::query()->where('slug', 'the-roman-world')->sole();
        $this->assertSame($id, $row->collection_id, 'upserted by slug');
        $this->assertSame('Rome', $row->title);
        $this->assertEquals([['kind' => 'tag', 'ref' => 'europe']], $row->items);
        $this->assertNull($row->cover_entity_id, 'no entity carries Q2277 here');
        $this->assertTrue(Collection::query()->where('slug', 'silk-roads')->exists(), 'a removed file deletes nothing');
    }

    public function test_a_draft_is_stored_but_not_published(): void
    {
        $this->write($this->set(['status' => 'draft']));

        $this->assertSame(0, $this->sync()[0]);

        $this->assertSame(CollectionStatus::Draft, Collection::query()->sole()->status);
        $this->assertSame(0, Collection::query()->published()->count());
    }

    public function test_an_invalid_file_is_reported_and_the_others_still_load(): void
    {
        $this->write($this->set(['slug' => 'aaa-broken', 'items' => [
            ['kind' => 'entity', 'ref' => 'Roman Empire'],
            ['kind' => 'person', 'ref' => 'caesar'],
            ['kind' => 'tag', 'ref' => 'classical'],
            ['kind' => 'tag', 'ref' => 'classical'],
        ]]));
        $this->write($this->set(['slug' => 'wrong-name']), 'other-name');
        File::put($this->dir.'/bad-json.json', '{"slug": ');
        $this->write($this->set(['slug' => 'typo', 'cover' => 'Q1']));
        $this->write($this->set());

        [$code, $output] = $this->sync();

        $this->assertSame(1, $code);
        foreach (['aaa-broken', 'other-name', 'bad-json', 'typo'] as $file) {
            $this->assertMatchesRegularExpression("/{$file} \\.+ invalid/", $output);
        }
        $this->assertMatchesRegularExpression('/the-roman-world \.+ created/', $output);
        foreach ([
            "items.0: an entity ref is a Wikidata id (Q123) or an entity uuid, not 'Roman Empire'",
            'The selected items.1.kind is invalid.',
            "items.3: tag 'classical' is already item 2",
            "slug 'wrong-name' must match the file name 'other-name'",
            'bad-json: not a JSON object',
            "typo: unknown field 'cover'",
        ] as $message) {
            $this->assertStringContainsString($message, $output);
        }
        $this->assertSame(['the-roman-world'], Collection::query()->pluck('slug')->all());
    }

    public function test_a_cover_given_as_a_uuid_or_naming_no_entity(): void
    {
        $rome = Entity::factory()->create(['wikidata_id' => null]);
        $this->write($this->set(['cover_qid' => strtoupper($rome->entity_id)]));
        $this->write($this->set(['slug' => 'silk-roads', 'cover_qid' => 'Q999999999']));

        [$code, $output] = $this->sync();

        $this->assertSame(0, $code);
        $this->assertStringContainsString('silk-roads: cover_qid Q999999999: no such entity, so no cover', $output);

        $this->assertSame($rome->entity_id, Collection::query()->where('slug', 'the-roman-world')->value('cover_entity_id'));
        $this->assertNull(Collection::query()->where('slug', 'silk-roads')->value('cover_entity_id'));
    }

    public function test_the_seed_collections_are_valid(): void
    {
        [$code, $output] = $this->sync('');

        $this->assertSame(0, $code, $output);
        $this->assertGreaterThanOrEqual(5, Collection::query()->published()->count());
    }
}
