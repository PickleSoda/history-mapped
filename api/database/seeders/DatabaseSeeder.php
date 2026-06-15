<?php

declare(strict_types=1);

namespace Database\Seeders;

use App\Models\User;
use Illuminate\Database\Seeder;

class DatabaseSeeder extends Seeder
{
    /**
     * Seed the application's database.
     */
    public function run(): void
    {
        // ── Roles + permissions must exist before users are assigned them ──

        $this->call(RoleSeeder::class);
        $this->call(PermissionSeeder::class);

        // ── Named users (one per role, known credentials for dev) ────

        User::factory()->admin()->create([
            'name' => 'Admin User',
            'email' => 'admin@example.com',
        ]);

        User::factory()->moderator()->create([
            'name' => 'Moderator User',
            'email' => 'moderator@example.com',
        ]);

        User::factory()->geoModerator()->create([
            'name' => 'Geo Moderator',
            'email' => 'geo@example.com',
        ]);

        User::factory()->historyModerator()->create([
            'name' => 'History Moderator',
            'email' => 'history@example.com',
        ]);

        User::factory()->create([
            'name' => 'Regular User',
            'email' => 'user@example.com',
        ])->assignRole('user');

        // ── Reference data ──────────────────────────────────────────

        $this->call(ReferenceTableSeeder::class);

        // ── Entity seed data ────────────────────────────────────────

        $this->call(EntitySeeder::class);

        // ── Relationships between entities ──────────────────────────

        $this->call(RelationshipSeeder::class);

        // ── Chronicle seed data ────────────────────────────────────

        $this->call(ChronicleSeeder::class);
    }
}
