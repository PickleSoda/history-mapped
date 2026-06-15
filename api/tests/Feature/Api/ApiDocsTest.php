<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

/**
 * OpenAPI documentation (Scramble): the spec is generated for the public /api/v1
 * contract, documents the Sanctum security scheme, and is access-controlled
 * outside local dev via the `viewApiDocs` gate.
 */
class ApiDocsTest extends TestCase
{
    use RefreshDatabase;

    public function test_openapi_spec_is_generated_and_scoped_to_v1(): void
    {
        config(['scramble.docs_public' => true]);

        $json = $this->getJson('/docs/api.json')->assertOk()->json();

        $this->assertArrayHasKey('openapi', $json);
        $this->assertArrayHasKey('paths', $json);

        $body = json_encode($json);
        $this->assertStringContainsString('entities', $body);
        $this->assertStringContainsString('chronicles', $body);
    }

    public function test_spec_documents_the_sanctum_bearer_security_scheme(): void
    {
        config(['scramble.docs_public' => true]);

        $json = $this->getJson('/docs/api.json')->assertOk()->json();

        $schemes = $json['components']['securitySchemes'] ?? [];
        $hasBearer = collect($schemes)->contains(
            fn ($scheme) => ($scheme['type'] ?? null) === 'http'
                && ($scheme['scheme'] ?? null) === 'bearer'
        );

        $this->assertTrue($hasBearer, 'Expected an HTTP bearer security scheme in the spec.');
    }

    public function test_docs_are_forbidden_for_guests_when_not_public(): void
    {
        // The testing environment is not `local`, so the viewApiDocs gate applies.
        config(['scramble.docs_public' => false]);

        $this->get('/docs/api')->assertForbidden();
        $this->get('/docs/api.json')->assertForbidden();
    }

    public function test_admin_can_view_the_docs(): void
    {
        config(['scramble.docs_public' => false]);

        $this->actingAs($this->userWithRole('admin'))
            ->get('/docs/api')
            ->assertOk();
    }

    public function test_non_admin_user_cannot_view_the_docs(): void
    {
        config(['scramble.docs_public' => false]);

        $this->actingAs($this->userWithRole('user'))
            ->get('/docs/api')
            ->assertForbidden();
    }

    public function test_docs_public_flag_opens_the_docs_to_guests(): void
    {
        config(['scramble.docs_public' => true]);

        $this->get('/docs/api')->assertOk();
    }
}
