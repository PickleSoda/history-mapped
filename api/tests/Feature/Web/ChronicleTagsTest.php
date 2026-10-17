<?php

declare(strict_types=1);

namespace Tests\Feature\Web;

use App\Actions\Tag\SyncTagsAction;
use App\Enums\TagSource;
use App\Models\Chronicle;
use Database\Seeders\TagSeeder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

class ChronicleTagsTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->seed(TagSeeder::class);
        $this->actingAs($this->userWithRole('admin'));
    }

    public function test_admin_update_makes_tags_manual_and_implies_ancestors(): void
    {
        $chronicle = Chronicle::factory()->create(['slug' => 'tang']);
        app(SyncTagsAction::class)($chronicle, ['japan', 'polity'], TagSource::Curated);

        $this->put(route('chronicles.update', 'tang'), [
            'title' => $chronicle->title,
            'slug' => 'tang',
            'tags' => ['China', 'medieval', 'Silk trade'],
        ])->assertRedirect();

        $rows = DB::table('chronicle_tags')->where('chronicle_id', $chronicle->chronicle_id)->orderBy('tag')->get();
        $this->assertSame(['asia', 'china', 'east-asia', 'medieval', 'silk-trade'], $rows->pluck('tag')->all());
        $this->assertSame(['manual'], $rows->pluck('source')->unique()->values()->all());
    }

    public function test_index_filters_by_tag_and_reports_flat_pagination(): void
    {
        $tang = Chronicle::factory()->create(['title' => 'Tang China']);
        Chronicle::factory()->create(['title' => 'Untagged']);
        app(SyncTagsAction::class)($tang, ['china', 'medieval'], TagSource::Curated);

        $this->get(route('chronicles.index', ['tags' => ['east-asia']]))
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('chronicles/index')
                ->where('chronicles.total', 1)
                ->where('chronicles.last_page', 1)
                ->where('chronicles.data.0.title', 'Tang China')
                // Leaf tags only: east-asia and asia are implied by china.
                ->where('chronicles.data.0.tags', ['medieval', 'china'])
                ->where('filters.tags', ['east-asia'])
                ->has('tagOptions'));
    }

    public function test_edit_page_receives_leaf_tags_and_options(): void
    {
        $chronicle = Chronicle::factory()->create(['slug' => 'han']);
        app(SyncTagsAction::class)($chronicle, ['china', 'classical'], TagSource::Curated);

        $this->get(route('chronicles.edit', 'han'))
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('chronicles/edit')
                ->where('chronicle.tags', ['classical', 'china'])
                ->where('tagOptions.0.slug', 'prehistory'));
    }
}
