<?php

declare(strict_types=1);

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

class ChronicleExtendedFieldsTest extends TestCase
{
    use RefreshDatabase;

    public function test_chronicle_extended_fields_round_trip_via_web_and_api(): void
    {
        $user = $this->userWithRole('admin');
        $this->actingAs($user);

        $chronicleId = Str::uuid()->toString();
        $entryId = Str::uuid()->toString();
        $relationshipId = Str::uuid()->toString();

        $payload = [
            'title' => 'Test Chronicle with Extended Fields',
            'slug' => 'test-chronicle-extended',
            'source_type' => 'video_transcript',
            'status' => 'draft',
            'start_year' => -1200,
            'end_year' => -1100,
            'impact_score' => 8,
            'approximate_location' => ['lat' => 30, 'lng' => 31],
            'entries' => [
                [
                    'sequence_order' => 0,
                    'narrative_text' => 'First entry with extended fields',
                    'start_year' => -1150,
                    'end_year' => -1140,
                    'impact_score' => 5,
                    'approximate_location' => ['lat' => 30, 'lng' => 31],
                ],
            ],
        ];

        // POST via Web
        $response = $this->post(route('chronicles.store'), $payload);
        $response->assertRedirect();

        // GET via Web
        $webResponse = $this->get(route('chronicles.show', 'test-chronicle-extended'));
        $webResponse->assertOk();
        $webResponse->assertInertia(fn (Assert $page) => $page
            ->has('chronicle', fn (Assert $page) => $page
                ->where('start_year', -1200)
                ->where('end_year', -1100)
                ->where('impact_score', 8)
                ->where('approximate_location', ['lat' => 30, 'lng' => 31])
                ->has('entries', 1, fn (Assert $page) => $page
                    ->where('start_year', -1150)
                    ->where('end_year', -1140)
                    ->where('impact_score', 5)
                    ->where('approximate_location', ['lat' => 30, 'lng' => 31])
                    ->etc()
                )
                ->etc()
            )
        );

        // GET via API
        $apiResponse = $this->getJson(route('api.v1.chronicles.show', 'test-chronicle-extended'));
        $apiResponse->assertOk();
        $apiResponse->assertJsonPath('data.start_year', -1200);
        $apiResponse->assertJsonPath('data.end_year', -1100);
        $apiResponse->assertJsonPath('data.impact_score', 8);
        $apiResponse->assertJsonPath('data.approximate_location', ['lat' => 30, 'lng' => 31]);
        $apiResponse->assertJsonPath('data.entries.0.start_year', -1150);
        $apiResponse->assertJsonPath('data.entries.0.end_year', -1140);
        $apiResponse->assertJsonPath('data.entries.0.impact_score', 5);
        $apiResponse->assertJsonPath('data.entries.0.approximate_location', ['lat' => 30, 'lng' => 31]);
    }
}
