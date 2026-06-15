<?php

declare(strict_types=1);

namespace Database\Seeders;

use Illuminate\Database\Seeder;
use Spatie\Permission\Models\Permission;
use Spatie\Permission\Models\Role;
use Spatie\Permission\PermissionRegistrar;

class PermissionSeeder extends Seeder
{
    /**
     * Editorial write permissions. Public `/api/v1` GET reads are intentionally
     * NOT gated by any permission — only CRUD/write operations require them.
     *
     * The `admin` role is granted everything via a Gate::before super-user check
     * (see AppServiceProvider), so it is not listed in the matrix below.
     */
    public const PERMISSIONS = [
        'entities.write',        // create/update/delete entities
        'entities.verify',       // change verification_status (sensitive promotion)
        'relationships.write',   // create/update/delete relationships
        'geometry.write',        // geometry periods, geo-references, OHM feature resolution
        'chronicles.write',      // create/update/delete chronicles + entries
        'sources.write',         // create/update sources
        'reference.manage',      // reference-table admin + cache clearing
    ];

    /**
     * Role → permission matrix. Tune as the editorial workflow matures.
     */
    public const ROLE_PERMISSIONS = [
        'moderator' => [
            'entities.write', 'entities.verify', 'relationships.write',
            'chronicles.write', 'sources.write',
        ],
        'history_moderator' => [
            'entities.write', 'relationships.write', 'chronicles.write', 'sources.write',
        ],
        'geo_moderator' => [
            'geometry.write',
        ],
        'user' => [],
    ];

    public function run(): void
    {
        // Clear spatie's permission cache so freshly-seeded permissions resolve
        // immediately (important in tests using RefreshDatabase).
        app(PermissionRegistrar::class)->forgetCachedPermissions();

        foreach (self::PERMISSIONS as $name) {
            Permission::firstOrCreate(['name' => $name]);
        }

        foreach (self::ROLE_PERMISSIONS as $roleName => $permissions) {
            $role = Role::firstOrCreate(['name' => $roleName]);
            $role->syncPermissions($permissions);
        }

        app(PermissionRegistrar::class)->forgetCachedPermissions();
    }
}
