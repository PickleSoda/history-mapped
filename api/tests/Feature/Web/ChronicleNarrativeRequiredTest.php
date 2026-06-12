<?php

declare(strict_types=1);

namespace Tests\Feature\Web;

use App\Models\Chronicle;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ChronicleNarrativeRequiredTest extends TestCase
{
    use RefreshDatabase;

    public function test_store_chronicle_requires_narrative_text_in_entries(): void
    {
        $user = User::factory()->create();
        $this->actingAs($user);

        $response = $this->post(route('chronicles.store'), [
            'title' => 'Test Chronicle',
            'source_type' => 'video_transcript',
            'entries' => [
                [
                    'sequence_order' => 1,
                ]
            ]
        ]);

        $response->assertSessionHasErrors(['entries.0.narrative_text']);
    }

    public function test_update_chronicle_requires_narrative_text_in_entries(): void
    {
        $user = User::factory()->create();
        $this->actingAs($user);

        $chronicle = Chronicle::factory()->create([
            'slug' => 'test-chronicle',
        ]);

        $response = $this->put(route('chronicles.update', $chronicle->slug), [
            'title' => 'Updated Chronicle',
            'entries' => [
                [
                    'sequence_order' => 1,
                ]
            ]
        ]);

        $response->assertSessionHasErrors(['entries.0.narrative_text']);
    }
}
