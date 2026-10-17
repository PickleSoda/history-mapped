<?php

use App\Models\User;
use Database\Seeders\PermissionSeeder;
use Database\Seeders\RoleSeeder;
use Illuminate\Database\Migrations\Migration;
use Spatie\Permission\PermissionRegistrar;

/**
 * Deploys only run `migrate`, so seed the roles + permissions here (both
 * seeders are idempotent) — including the new `admin.access` and
 * `contributions.*` permissions.
 *
 * The admin panel used to be readable by any signed-in user and is now gated
 * by `admin.access`. Users that predate this migration and hold no role keep
 * exactly that: the default `user` role plus a direct `admin.access` grant.
 * New registrations get only the `user` role.
 */
return new class extends Migration
{
    public function up(): void
    {
        (new RoleSeeder)->run();
        (new PermissionSeeder)->run();

        User::query()->whereDoesntHave('roles')->each(function (User $user): void {
            $user->assignRole('user');
            $user->givePermissionTo('admin.access');
        });

        app(PermissionRegistrar::class)->forgetCachedPermissions();
    }

    public function down(): void
    {
        // Roles/permissions are reference data shared with the seeders; leave them.
    }
};
