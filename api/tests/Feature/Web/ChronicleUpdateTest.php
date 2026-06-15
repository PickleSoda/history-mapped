<?php

declare(strict_types=1);

namespace Tests\Feature\Web;

use App\Models\Chronicle;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ChronicleUpdateTest extends TestCase
{
    use RefreshDatabase;

    public function test_update_chronicle_with_same_slug_does_not_throw_500(): void
    {
        $user = $this->userWithRole('admin');
        $this->actingAs($user);

        $chronicle = Chronicle::factory()->create([
            'slug' => 'test-chronicle-slug',
            'title' => 'Original Title',
        ]);

        $response = $this->put(route('chronicles.update', $chronicle->slug), [
            'title' => 'Updated Title',
            'slug' => 'test-chronicle-slug',
        ]);

        $response->assertRedirect();
        $response->assertSessionHas('success', 'Chronicle updated successfully.');
    }
}
