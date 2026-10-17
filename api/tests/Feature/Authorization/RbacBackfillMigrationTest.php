<?php

declare(strict_types=1);

namespace Tests\Feature\Authorization;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

/**
 * The 2026-10-18 migration gates the admin panel behind `admin.access`; users
 * that predate it must keep the read access they had.
 */
class RbacBackfillMigrationTest extends TestCase
{
    use RefreshDatabase;

    private function runMigration(): void
    {
        $migration = require database_path('migrations/2026_10_18_000003_seed_rbac_and_backfill_user_roles.php');
        $migration->up();
    }

    public function test_role_less_users_keep_admin_read_access(): void
    {
        $legacy = User::factory()->create();
        $moderator = $this->userWithRole('moderator');

        $this->runMigration();

        $legacy->refresh();
        $this->assertSame(['user'], $legacy->getRoleNames()->all());
        $this->assertTrue($legacy->can('admin.access'));
        $this->assertFalse($legacy->can('entities.write'));
        $this->actingAs($legacy)->get(route('dashboard'))->assertOk();

        // Users that already had a role are left alone.
        $this->assertSame(['moderator'], $moderator->fresh()->getRoleNames()->all());
        $this->assertFalse($moderator->fresh()->hasDirectPermission('admin.access'));
    }

    public function test_it_is_idempotent(): void
    {
        $this->runMigration();
        $this->runMigration();

        $this->assertDatabaseCount('roles', 5);
    }
}
