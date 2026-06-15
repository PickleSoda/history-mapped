<?php

namespace Tests;

use App\Models\User;
use Database\Seeders\PermissionSeeder;
use Database\Seeders\RoleSeeder;
use Illuminate\Foundation\Testing\TestCase as BaseTestCase;
use Laravel\Fortify\Features;

abstract class TestCase extends BaseTestCase
{
    protected function skipUnlessFortifyFeature(string $feature, ?string $message = null): void
    {
        if (! Features::enabled($feature)) {
            $this->markTestSkipped($message ?? "Fortify feature [{$feature}] is not enabled.");
        }
    }

    /**
     * Seed RBAC roles + permissions (idempotent). Safe to call repeatedly.
     */
    protected function seedRbac(): void
    {
        $this->seed(RoleSeeder::class);
        $this->seed(PermissionSeeder::class);
    }

    /**
     * Create a verified user with the given role (default: admin, which bypasses
     * all permission checks). Use for tests that exercise an authorised editor.
     */
    protected function userWithRole(string $role = 'admin'): User
    {
        $this->seedRbac();

        return User::factory()->create()->assignRole($role);
    }

    /**
     * Create a verified user granted exactly the given permissions (no role).
     * Use for fine-grained authorization assertions.
     *
     * @param  array<int, string>  $permissions
     */
    protected function userWithPermissions(array $permissions): User
    {
        $this->seedRbac();

        return User::factory()->create()->givePermissionTo($permissions);
    }
}
