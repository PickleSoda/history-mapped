<?php

declare(strict_types=1);

namespace Tests\Feature\Ai;

use App\Enums\EntityType;
use App\Models\Chronicle;
use App\Models\Entity;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

class AiContextPropTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();
        $this->user = $this->userWithRole('admin');
    }

    public function test_entity_show_includes_ai_context(): void
    {
        $entity = Entity::factory()
            ->ofType(EntityType::Person)
            ->create(['name' => 'Julius Caesar']);

        $this->actingAs($this->user)
            ->get(route('entities.show', $entity->entity_id))
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('ai_context.type', 'entity')
                ->where('ai_context.id', $entity->entity_id)
            );
    }

    public function test_entity_edit_includes_ai_context(): void
    {
        $entity = Entity::factory()
            ->ofType(EntityType::City)
            ->create(['name' => 'Rome']);

        $this->actingAs($this->user)
            ->get(route('entities.edit', $entity->entity_id))
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('ai_context.type', 'entity')
                ->where('ai_context.id', $entity->entity_id)
            );
    }

    public function test_chronicle_show_includes_ai_context(): void
    {
        $chronicle = Chronicle::factory()->create([
            'title' => 'Rise of Rome',
            'slug' => 'rise-of-rome',
        ]);

        $this->actingAs($this->user)
            ->get(route('chronicles.show', $chronicle->slug))
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('ai_context.type', 'chronicle')
                ->where('ai_context.id', $chronicle->chronicle_id)
            );
    }

    public function test_chronicle_edit_includes_ai_context(): void
    {
        $chronicle = Chronicle::factory()->create([
            'title' => 'Fall of Rome',
            'slug' => 'fall-of-rome',
        ]);

        $this->actingAs($this->user)
            ->get(route('chronicles.edit', $chronicle->slug))
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('ai_context.type', 'chronicle')
                ->where('ai_context.id', $chronicle->chronicle_id)
            );
    }
}
