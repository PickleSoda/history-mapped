<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\RateLimiter;
use Tests\TestCase;

class ApiRateLimitTest extends TestCase
{
    use RefreshDatabase;

    public function test_the_public_api_is_rate_limited_per_client(): void
    {
        config(['app.api_rate_limit' => 2]);
        RateLimiter::clear('api');

        $this->getJson('/api/v1/tags')->assertOk()->assertHeader('X-RateLimit-Limit', '2');
        $this->getJson('/api/v1/tags')->assertOk()->assertHeader('X-RateLimit-Remaining', '0');
        $this->getJson('/api/v1/tags')->assertTooManyRequests();

        // Another client has its own budget.
        $this->withServerVariables(['REMOTE_ADDR' => '203.0.113.9'])
            ->getJson('/api/v1/tags')
            ->assertOk();
    }
}
