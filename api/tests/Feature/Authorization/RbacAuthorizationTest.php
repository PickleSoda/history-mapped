<?php

declare(strict_types=1);

namespace Tests\Feature\Authorization;

use App\Enums\VerificationStatus;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Testing\TestResponse;
use Tests\TestCase;

/**
 * RBAC: public /api/v1 reads stay open; every write is permission-gated.
 */
class RbacAuthorizationTest extends TestCase
{
    use RefreshDatabase;

    /** The gate let the request through to the controller/validation layer. */
    private function assertGatePassed(TestResponse $response): void
    {
        $this->assertNotContains(
            $response->getStatusCode(),
            [401, 403],
            "Expected the authorization gate to pass, got {$response->getStatusCode()}."
        );
    }

    // ── Public reads ──────────────────────────────────────────────────────

    public function test_public_reads_require_no_authentication(): void
    {
        $this->getJson(route('api.v1.entities.index'))->assertOk();
        $this->getJson(route('api.v1.chronicles.index'))->assertOk();
        $this->getJson(route('api.v1.reference.index'))->assertOk();
    }

    // ── Authentication is still required for writes ───────────────────────

    public function test_api_write_requires_authentication(): void
    {
        $this->postJson(route('api.v1.entities.store'), [])->assertUnauthorized();
        $this->postJson(route('api.v1.map.resolve-ohm-feature'), [])->assertUnauthorized();
    }

    // ── Permission gating on writes ───────────────────────────────────────

    public function test_authenticated_user_without_permission_is_forbidden(): void
    {
        $user = $this->userWithRole('user'); // authenticated, no write permissions

        $this->actingAs($user)
            ->postJson(route('api.v1.entities.store'), [])
            ->assertForbidden();
    }

    public function test_user_with_permission_passes_the_gate(): void
    {
        $user = $this->userWithPermissions(['entities.write']);

        $this->assertGatePassed(
            $this->actingAs($user)->postJson(route('api.v1.entities.store'), [])
        );
    }

    // ── Role scoping ──────────────────────────────────────────────────────

    public function test_geo_moderator_can_write_geometry_but_not_entities(): void
    {
        $entity = Entity::factory()->create();
        $geo = $this->userWithRole('geo_moderator');

        $this->actingAs($geo)
            ->postJson(route('api.v1.entities.store'), [])
            ->assertForbidden();

        $this->assertGatePassed(
            $this->actingAs($geo)->postJson(
                route('api.v1.entities.geography-references.store', $entity),
                []
            )
        );
    }

    public function test_history_moderator_can_write_entities_but_not_geometry(): void
    {
        $entity = Entity::factory()->create();
        $hist = $this->userWithRole('history_moderator');

        $this->assertGatePassed(
            $this->actingAs($hist)->postJson(route('api.v1.entities.store'), [])
        );

        $this->actingAs($hist)
            ->postJson(route('api.v1.entities.geography-references.store', $entity), [])
            ->assertForbidden();
    }

    // ── Admin super-user bypass ───────────────────────────────────────────

    public function test_admin_bypasses_every_permission_check(): void
    {
        $entity = Entity::factory()->create();
        $admin = $this->userWithRole('admin');

        $this->assertGatePassed(
            $this->actingAs($admin)->postJson(route('api.v1.entities.store'), [])
        );
        $this->assertGatePassed(
            $this->actingAs($admin)->postJson(
                route('api.v1.entities.geography-references.store', $entity),
                []
            )
        );
        $this->assertGatePassed(
            $this->actingAs($admin)->postJson(route('api.v1.map.resolve-ohm-feature'), [])
        );
    }

    // ── resolve-ohm-feature is now an editorial (geometry) endpoint ───────

    public function test_resolve_ohm_feature_requires_geometry_permission(): void
    {
        $this->actingAs($this->userWithRole('user'))
            ->postJson(route('api.v1.map.resolve-ohm-feature'), [])
            ->assertForbidden();

        $this->assertGatePassed(
            $this->actingAs($this->userWithRole('geo_moderator'))
                ->postJson(route('api.v1.map.resolve-ohm-feature'), [])
        );
    }

    // ── entities.verify gate (web admin update) ───────────────────────────

    public function test_changing_verification_status_requires_verify_permission(): void
    {
        $entity = Entity::factory()->create([
            'verification_status' => VerificationStatus::PipelineDraft->value,
        ]);

        // history_moderator has entities.write but NOT entities.verify.
        $hist = $this->userWithRole('history_moderator');

        // Promoting the verification status is forbidden.
        $this->actingAs($hist)
            ->put(route('entities.update', $entity->entity_id), [
                'verification_status' => VerificationStatus::HumanVerified->value,
            ])
            ->assertForbidden();

        // Editing without touching the verification status is allowed by the gate.
        $this->assertGatePassed(
            $this->actingAs($hist)->put(route('entities.update', $entity->entity_id), [
                'summary' => 'An edit that leaves verification untouched.',
            ])
        );
    }

    public function test_admin_may_change_verification_status(): void
    {
        $entity = Entity::factory()->create([
            'verification_status' => VerificationStatus::PipelineDraft->value,
        ]);
        $admin = $this->userWithRole('admin');

        $this->assertGatePassed(
            $this->actingAs($admin)->put(route('entities.update', $entity->entity_id), [
                'verification_status' => VerificationStatus::HumanVerified->value,
            ])
        );
    }
}
