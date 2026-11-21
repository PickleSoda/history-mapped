<?php

declare(strict_types=1);

namespace Tests\Feature;

use Tests\TestCase;

/**
 * The public site calls the API from another origin (config/cors.php). Before
 * a write the browser asks permission with an OPTIONS preflight; the answer
 * says how long it may be remembered.
 */
class CorsPreflightTest extends TestCase
{
    public function test_a_preflight_from_the_site_is_allowed_and_may_be_remembered(): void
    {
        $origin = 'https://atlas.test';
        config(['cors.allowed_origins' => [$origin]]);

        $response = $this->call('OPTIONS', '/api/v1/me/stars', server: [
            'HTTP_ORIGIN' => $origin,
            'HTTP_ACCESS_CONTROL_REQUEST_METHOD' => 'POST',
            'HTTP_ACCESS_CONTROL_REQUEST_HEADERS' => 'content-type, x-xsrf-token',
        ]);

        $response->assertNoContent();
        $response->assertHeader('Access-Control-Allow-Origin', $origin);
        $response->assertHeader('Access-Control-Allow-Credentials', 'true');
        $response->assertHeader('Access-Control-Max-Age', '7200');
    }

    public function test_a_preflight_from_another_origin_gets_no_permission(): void
    {
        config(['cors.allowed_origins' => ['https://atlas.test']]);

        $response = $this->call('OPTIONS', '/api/v1/me/stars', server: [
            'HTTP_ORIGIN' => 'https://elsewhere.test',
            'HTTP_ACCESS_CONTROL_REQUEST_METHOD' => 'POST',
        ]);

        $this->assertNotSame('https://elsewhere.test', $response->headers->get('Access-Control-Allow-Origin'));
    }
}
