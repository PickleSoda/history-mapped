<?php

declare(strict_types=1);

namespace Tests\Feature\Images;

use App\Actions\Entity\FetchEntityImagesAction;
use App\Enums\EntityType;
use App\Models\Entity;
use App\Services\WikimediaImages;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

class EntityImagesTest extends TestCase
{
    use RefreshDatabase;

    /** Commons files the fake knows; anything else comes back missing. */
    private const FILES = [
        'Hagia Sophia Mars 2013.jpg' => ['license' => 'CC BY-SA 3.0', 'artist' => '<a href="//commons.wikimedia.org/wiki/User:A">Arild V&aring;gen</a>'],
        'Arms.svg' => ['license' => 'Public domain', 'artist' => null],
        'Portrait.jpg' => ['license' => 'CC BY 4.0', 'artist' => 'Painter'],
    ];

    /**
     * Fakes the three Wikimedia endpoints:
     *  Q1 (city): P18 + coat of arms (+ a P41 file that is missing on Commons)
     *  Q2 (person): no P18; its Wikipedia lead image is on Commons
     *  Q3 (battle): no claims; its Wikipedia lead image is a local enwiki file
     */
    private function fakeWikimedia(): void
    {
        Http::fake(function (Request $request) {
            $host = parse_url($request->url(), PHP_URL_HOST);
            $data = $request->data();

            return match ($host) {
                'query.wikidata.org' => Http::response(['results' => ['bindings' => $this->sparqlRows($data['query'])]]),
                'en.wikipedia.org' => Http::response(['query' => ['pages' => [
                    ['title' => 'Someone', 'pageimage' => 'Portrait.jpg', 'original' => ['source' => 'https://upload.wikimedia.org/wikipedia/commons/a/ab/Portrait.jpg']],
                    ['title' => 'Nothing Article', 'pageimage' => 'Local.jpg', 'original' => ['source' => 'https://upload.wikimedia.org/wikipedia/en/a/ab/Local.jpg']],
                ]]]),
                'commons.wikimedia.org' => Http::response(['query' => ['pages' => array_map(
                    $this->commonsPage(...),
                    explode('|', $data['titles'] ?? ''),
                )]]),
                default => Http::response([], 404),
            };
        });
    }

    /** @return list<array<string, array{value: string}>> */
    private function sparqlRows(string $query): array
    {
        $file = fn (string $qid, string $p, string $name) => [
            'item' => ['value' => "http://www.wikidata.org/entity/{$qid}"],
            'prop' => ['value' => "http://www.wikidata.org/prop/direct/{$p}"],
            'file' => ['value' => 'http://commons.wikimedia.org/wiki/Special:FilePath/'.rawurlencode($name)],
        ];
        $title = fn (string $qid, string $t) => ['item' => ['value' => "http://www.wikidata.org/entity/{$qid}"], 'title' => ['value' => $t]];

        $rows = [];
        if (str_contains($query, 'wd:Q1 ') || str_contains($query, 'wd:Q1 }')) {
            $rows[] = $file('Q1', 'P18', 'Hagia Sophia Mars 2013.jpg');
            $rows[] = $file('Q1', 'P94', 'Arms.svg');
            $rows[] = $file('Q1', 'P41', 'Gone.svg');
            $rows[] = $title('Q1', 'Hagia Sophia');
        }
        if (str_contains($query, 'wd:Q2')) {
            $rows[] = $title('Q2', 'Someone');
        }
        if (str_contains($query, 'wd:Q3')) {
            $rows[] = $title('Q3', 'Nothing Article');
        }

        return $rows;
    }

    /** @return array<string, mixed> */
    private function commonsPage(string $title): array
    {
        $name = substr($title, 5);
        $meta = self::FILES[$name] ?? null;
        if ($meta === null) {
            return ['title' => $title, 'missing' => true];
        }

        $path = str_replace(' ', '_', $name);

        return ['title' => $title, 'imageinfo' => [[
            'mime' => str_ends_with($name, '.svg') ? 'image/svg+xml' : 'image/jpeg',
            'width' => 4000,
            'height' => 3000,
            'url' => "https://upload.wikimedia.org/wikipedia/commons/a/ab/{$path}",
            'thumburl' => "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/{$path}/960px-{$path}?utm_source=commons.wikimedia.org&utm_campaign=imageinfo",
            'thumbwidth' => 960,
            'thumbheight' => 720,
            'descriptionurl' => "https://commons.wikimedia.org/wiki/File:{$path}",
            'extmetadata' => array_filter([
                'LicenseShortName' => ['value' => $meta['license']],
                'Artist' => $meta['artist'] !== null ? ['value' => $meta['artist']] : null,
                'AttributionRequired' => ['value' => $meta['license'] === 'Public domain' ? 'false' : 'true'],
            ]),
        ]]];
    }

    private function entity(string $qid, EntityType $type, array $attributes = []): Entity
    {
        $entity = Entity::factory()->ofType($type)->create(['wikidata_id' => $qid]);
        // Raw write: the factory's pre-encoded string would be stored as a JSON string.
        DB::table('entities')->where('entity_id', $entity->entity_id)
            ->update(['attributes' => json_encode($attributes ?: ['entity_color' => '#123456'])]);

        return $entity->refresh();
    }

    private function media(Entity $entity): mixed
    {
        return json_decode((string) DB::table('entities')->where('entity_id', $entity->entity_id)->value('attributes'), true)['media_refs'] ?? null;
    }

    public function test_command_links_commons_images_with_credits_and_marks_empty_checks(): void
    {
        $this->fakeWikimedia();
        $city = $this->entity('Q1', EntityType::City);
        $person = $this->entity('Q2', EntityType::Person);
        $battle = $this->entity('Q3', EntityType::EventBattle);

        $this->artisan('entity:fetch-images')->assertSuccessful();

        $images = $this->media($city);
        $this->assertSame(['image', 'coat_of_arms'], array_column($images, 'kind'), 'P18 first; the missing flag is dropped');
        $this->assertSame('https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/Hagia_Sophia_Mars_2013.jpg/960px-Hagia_Sophia_Mars_2013.jpg', $images[0]['url']);
        $this->assertSame('Arild Vågen', $images[0]['author']);
        $this->assertSame('CC BY-SA 3.0', $images[0]['license']);
        $this->assertTrue($images[0]['attribution_required']);
        $this->assertSame('https://commons.wikimedia.org/wiki/File:Hagia_Sophia_Mars_2013.jpg', $images[0]['page_url']);
        $this->assertSame(['wikidata', 'P18'], [$images[0]['source'], $images[0]['property']]);
        $this->assertFalse($images[1]['attribution_required']);

        $this->assertSame(['Portrait.jpg'], array_column($this->media($person), 'file'));
        $this->assertSame('wikipedia', $this->media($person)[0]['source']);

        // Local enwiki files are not used; the empty list records the check.
        $this->assertSame([], $this->media($battle));

        // Other attributes are untouched.
        $this->assertSame('#123456', $city->fresh()->attributes['entity_color']);
    }

    public function test_command_skips_checked_and_admin_curated_entities_unless_refreshing(): void
    {
        $this->fakeWikimedia();
        $checked = $this->entity('Q1', EntityType::City, ['media_refs' => []]);
        $curated = $this->entity('Q1', EntityType::City, ['media_refs' => [], FetchEntityImagesAction::CURATED_KEY => '2026-10-01T00:00:00+00:00']);

        $this->artisan('entity:fetch-images')->assertSuccessful();
        $this->assertSame([], $this->media($checked));

        $this->artisan('entity:fetch-images', ['--refresh' => true])->assertSuccessful();
        $this->assertCount(2, $this->media($checked));
        $this->assertSame([], $this->media($curated));
    }

    public function test_dry_run_writes_nothing(): void
    {
        $this->fakeWikimedia();
        $city = $this->entity('Q1', EntityType::City);

        $this->artisan('entity:fetch-images', ['--dry-run' => true])
            ->expectsOutputToContain('Hagia Sophia Mars 2013.jpg [CC BY-SA 3.0]')
            ->assertSuccessful();

        $this->assertNull($this->media($city));
    }

    public function test_admin_saves_commons_and_external_images_and_marks_entity_curated(): void
    {
        $this->fakeWikimedia();
        $this->actingAs($this->userWithRole('admin'));
        $entity = $this->entity('Q9', EntityType::Person);

        $this->putJson(route('entities.images.update', $entity), [
            'images' => [
                ['url' => 'https://commons.wikimedia.org/wiki/File:Portrait.jpg', 'kind' => 'image', 'caption' => 'A portrait'],
                ['url' => 'https://museum.example/scan.jpg', 'kind' => 'map', 'author' => 'Museum', 'license' => 'CC BY 4.0'],
            ],
        ])
            ->assertOk()
            ->assertJsonPath('data.0.file', 'Portrait.jpg')
            ->assertJsonPath('data.0.license', 'CC BY 4.0')
            ->assertJsonPath('data.0.author', 'Painter')
            ->assertJsonPath('data.0.caption', 'A portrait')
            ->assertJsonPath('data.1.source', 'external')
            ->assertJsonPath('data.1.page_url', 'https://museum.example/scan.jpg');

        $this->assertNotNull($entity->fresh()->attributes[FetchEntityImagesAction::CURATED_KEY] ?? null);
    }

    public function test_admin_save_rejects_unlicensed_external_and_missing_commons_files(): void
    {
        $this->fakeWikimedia();
        $this->actingAs($this->userWithRole('admin'));
        $entity = $this->entity('Q9', EntityType::Person);

        $this->putJson(route('entities.images.update', $entity), [
            'images' => [['url' => 'https://museum.example/scan.jpg', 'kind' => 'image']],
        ])->assertUnprocessable()->assertJsonValidationErrors('images.0.license');

        $this->putJson(route('entities.images.update', $entity), [
            'images' => [['file' => 'Gone.svg', 'kind' => 'flag']],
        ])->assertUnprocessable()->assertJsonValidationErrors('images.0.file');

        $this->assertNull($this->media($entity));
    }

    public function test_image_write_needs_entities_write_permission(): void
    {
        $this->actingAs($this->userWithPermissions(['admin.access']));
        $entity = $this->entity('Q9', EntityType::Person);

        $this->putJson(route('entities.images.update', $entity), ['images' => []])->assertForbidden();
        $this->getJson(route('entities.images.index', $entity))->assertOk()->assertJsonPath('data', []);
    }

    public function test_candidates_from_wikidata_and_wikipedia(): void
    {
        $this->fakeWikimedia();
        $this->actingAs($this->userWithRole('admin'));
        $entity = $this->entity('Q1', EntityType::City);

        $this->getJson(route('entities.images.candidates', [$entity, 'source' => 'wikidata']))
            ->assertOk()
            ->assertJsonCount(2, 'data')
            ->assertJsonPath('data.0.property', 'P18');

        $this->getJson(route('entities.images.candidates', [$entity, 'source' => 'url', 'q' => 'ftp://nope']))
            ->assertUnprocessable();
    }

    public function test_entity_saves_keep_linked_images(): void
    {
        $this->actingAs($this->userWithRole('admin'));
        $images = [['type' => 'image', 'kind' => 'image', 'url' => 'https://thumb.wikimedia.org/x.jpg']];
        $entity = $this->entity('Q9', EntityType::Person, ['media_refs' => $images, 'gender' => 'female']);

        // The admin form never sends media_refs …
        $this->get(route('entities.edit', $entity))->assertInertia(
            fn (Assert $page) => $page->missing('entity.attributes.media_refs')->where('entity.attributes.gender', 'female'),
        );

        // … and saving the form (attributes rewritten from its fields) keeps them.
        $this->put(route('entities.update', $entity), ['name' => 'Renamed', 'attributes' => ['gender' => 'male']])->assertRedirect();

        $this->assertEquals($images, $this->media($entity));
        $this->assertSame('male', $entity->fresh()->attributes['gender']);
    }

    public function test_pipeline_import_links_images_for_the_entities_it_imported(): void
    {
        config(['services.wikimedia.fetch_images_on_import' => true]);
        $this->fakeWikimedia();
        $older = $this->entity('Q2', EntityType::Person);
        DB::table('entities')->where('entity_id', $older->entity_id)->update(['updated_at' => now()->subHour()]);

        $path = sys_get_temp_dir().'/images_import_'.uniqid().'.jsonl';
        file_put_contents($path, json_encode([
            'name' => 'Hagia Sophia', 'entity_type' => 'infrastructure_monument', 'entity_group' => 'PLACE',
            'summary' => 's', 'wikidata_id' => 'Q1',
        ])."\n");

        $this->artisan('pipeline:import', ['path' => $path, '--sync' => true, '--skip-relationships' => true])
            ->expectsOutputToContain('Images: linked for 1 of 1 entities')
            ->assertExitCode(0);

        $imported = Entity::query()->where('wikidata_id', 'Q1')->sole();
        // Monuments don't use coats of arms (FetchEntityImagesAction::ORDER).
        $this->assertSame(['Hagia Sophia Mars 2013.jpg'], array_column($this->media($imported), 'file'));
        // Only this run's entities; older unchecked ones wait for entity:fetch-images.
        $this->assertNull($this->media($older));
    }

    public function test_pipeline_import_can_skip_images(): void
    {
        config(['services.wikimedia.fetch_images_on_import' => true]);
        Http::preventStrayRequests();

        $path = sys_get_temp_dir().'/images_import_'.uniqid().'.jsonl';
        file_put_contents($path, json_encode([
            'name' => 'Hagia Sophia', 'entity_type' => 'infrastructure_monument', 'entity_group' => 'PLACE',
            'summary' => 's', 'wikidata_id' => 'Q1',
        ])."\n");

        $this->artisan('pipeline:import', ['path' => $path, '--sync' => true, '--skip-relationships' => true, '--skip-images' => true])
            ->assertExitCode(0);

        $this->assertNull($this->media(Entity::query()->where('wikidata_id', 'Q1')->sole()));
    }

    public function test_admin_index_filters_by_image_presence(): void
    {
        $this->actingAs($this->userWithRole('admin'));
        $this->entity('Q1', EntityType::City, ['media_refs' => [['type' => 'image', 'url' => 'https://x.example/a.jpg']]])->update(['name' => 'Pictured']);
        $this->entity('Q2', EntityType::City, ['media_refs' => []])->update(['name' => 'Checked']);
        $this->entity('Q3', EntityType::City)->update(['name' => 'Unchecked']);

        $names = fn (string $image) => collect(
            $this->get(route('entities.index', ['image' => $image, 'sort' => 'name']))->viewData('page')['props']['entities']['data'],
        )->pluck('name')->sort()->values()->all();

        $this->assertSame(['Pictured'], $names('present'));
        $this->assertSame(['Checked', 'Unchecked'], $names('missing'));
    }

    public function test_file_names_are_read_from_wikimedia_urls(): void
    {
        $this->assertSame('Hagia Sophia Mars 2013.jpg', WikimediaImages::fileFromUrl('https://commons.wikimedia.org/wiki/File:Hagia_Sophia_Mars_2013.jpg'));
        $this->assertSame('Foo (1).png', WikimediaImages::fileFromUrl('https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Foo_%281%29.png/960px-Foo_%281%29.png'));
        $this->assertSame('Bar.jpg', WikimediaImages::fileFromUrl('https://en.wikipedia.org/wiki/File:Bar.jpg'));
        $this->assertNull(WikimediaImages::fileFromUrl('https://upload.wikimedia.org/wikipedia/en/a/ab/Local.jpg'));
        $this->assertNull(WikimediaImages::fileFromUrl('https://example.org/File:Bar.jpg'));
    }
}
