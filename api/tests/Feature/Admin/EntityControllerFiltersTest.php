<?php

declare(strict_types=1);

namespace Tests\Feature\Admin;

use App\Enums\EntityType;
use App\Enums\VerificationStatus;
use App\Models\Entity;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class EntityControllerFiltersTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();
        $this->user = User::factory()->create();
    }

    public function test_index_is_accessible_to_authenticated_users(): void
    {
        $this->actingAs($this->user)
            ->get(route('entities.index'))
            ->assertOk();
    }

    public function test_index_redirects_guests_to_login(): void
    {
        $this->get(route('entities.index'))
            ->assertRedirect(route('login'));
    }

    public function test_type_filter_restricts_results(): void
    {
        Entity::factory()->ofType(EntityType::City)->create(['name' => 'Rome']);
        Entity::factory()->ofType(EntityType::Person)->create(['name' => 'Caesar']);

        $response = $this->actingAs($this->user)
            ->get(route('entities.index', ['type' => EntityType::City->value]));

        $response->assertOk();
        $response->assertInertia(function ($page) {
            $data = $page->toArray()['props']['entities']['data'];
            $this->assertCount(1, $data);
            $this->assertSame('Rome', $data[0]['name']);
        });
    }

    public function test_date_from_filter_excludes_entities_before_range(): void
    {
        // Exists 500–100 BCE — should be excluded when from=0
        Entity::factory()->withTemporalRange('-500', '-100')->create(['name' => 'Ancient']);
        // Exists 100 CE – 500 CE — should be included
        Entity::factory()->withTemporalRange('100', '500')->create(['name' => 'Medieval']);

        $response = $this->actingAs($this->user)
            ->get(route('entities.index', ['date_from' => '0', 'date_to' => '1000']));

        $response->assertOk();
        $response->assertInertia(function ($page) {
            $names = array_column($page->toArray()['props']['entities']['data'], 'name');
            $this->assertContains('Medieval', $names);
            $this->assertNotContains('Ancient', $names);
        });
    }

    public function test_period_column_is_computed_from_temporal_start_end_when_display_range_is_null(): void
    {
        Entity::factory()
            ->withTemporalRange('-500', '-100')
            ->create(['name' => 'Rome', 'temporal_display_range' => null]);

        $response = $this->actingAs($this->user)
            ->get(route('entities.index'));

        $response->assertOk();
        $response->assertInertia(function ($page) {
            $entity = collect($page->toArray()['props']['entities']['data'])
                ->firstWhere('name', 'Rome');
            $this->assertNotNull($entity);
            $this->assertSame('500 BCE – 100 BCE', $entity['temporal_display_range']);
        });
    }

    public function test_filter_options_include_types(): void
    {
        $response = $this->actingAs($this->user)
            ->get(route('entities.index'));

        $response->assertOk();
        $response->assertInertia(function ($page) {
            $options = $page->toArray()['props']['filterOptions'];
            $this->assertArrayHasKey('types', $options);
            $this->assertNotEmpty($options['types']);
            $this->assertArrayHasKey('value', $options['types'][0]);
            $this->assertArrayHasKey('label', $options['types'][0]);
        });
    }

    public function test_active_filters_are_echoed_back_in_props(): void
    {
        $response = $this->actingAs($this->user)
            ->get(route('entities.index', [
                'type' => EntityType::City->value,
                'date_from' => '-100',
                'date_to' => '500',
            ]));

        $response->assertOk();
        $response->assertInertia(function ($page) {
            $filters = $page->toArray()['props']['filters'];
            $this->assertSame(EntityType::City->value, $filters['type']);
            $this->assertSame('-100', $filters['date_from']);
            $this->assertSame('500', $filters['date_to']);
        });
    }
}
