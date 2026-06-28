<?php

namespace Tests\Feature\Ai;

use App\Models\Ai\ProposedChange;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ProposedChangeModelTest extends TestCase
{
    use RefreshDatabase;

    public function test_a_change_has_parts_with_pending_status_and_array_casts(): void
    {
        $user = User::factory()->create();
        $change = ProposedChange::create([
            'user_id' => $user->id, 'context_type' => 'entity', 'context_id' => 'e-1',
        ]);
        $part = $change->parts()->create([
            'key' => 'a', 'tool' => 'create_entity',
            'payload' => ['name' => 'Tikal'], 'human_diff' => ['summary' => 'Create Tikal'],
        ]);

        $this->assertSame('pending', $part->fresh()->status);
        $this->assertSame('Tikal', $part->fresh()->payload['name']);
        $this->assertTrue($change->parts()->whereKey($part->id)->exists());

        $part->applyApplied('new-entity-id');
        $this->assertSame('applied', $part->fresh()->status);
        $this->assertSame('new-entity-id', $part->fresh()->result_id);
    }
}
