<?php

declare(strict_types=1);

namespace Database\Seeders;

use Illuminate\Database\Seeder;
use Spatie\Permission\Models\Role;

class RoleSeeder extends Seeder
{
    /**
     * Define the application roles.
     *
     * Roles are intentionally seeded without permissions for now;
     * policy enforcement is deferred to a future task.
     */
    public function run(): void
    {
        $roles = [
            'admin',
            'moderator',
            'geo_moderator',
            'history_moderator',
            'user',
        ];

        foreach ($roles as $role) {
            Role::firstOrCreate(['name' => $role]);
        }
    }
}
