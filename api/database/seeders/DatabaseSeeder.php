<?php

declare(strict_types=1);

namespace Database\Seeders;

use App\Models\User;
use Illuminate\Database\Seeder;

/**
 * Minimal "base" seed: everything the application needs to run, but NO
 * pipeline-authored content (entities, relationships, chronicles).
 *
 * Seeds roles, permissions, dev users, and curated reference tables only.
 * This is the default seed (`php artisan db:seed` / `migrate --seed`) and the
 * blank slate the agentic pipeline writes into.
 *
 * For the full demo dataset (entities / relationships / chronicles fixtures on
 * top of this base), seed {@see DemoSeeder} instead:
 *   php artisan db:seed --class=Database\\Seeders\\DemoSeeder
 *   php artisan migrate:fresh --seeder=Database\\Seeders\\DemoSeeder
 */
class DatabaseSeeder extends Seeder
{
    /**
     * Seed the application's database (minimal base).
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

        // ── Reference data (calendars, regions, periods, …) ─────────

        $this->call(ReferenceTableSeeder::class);

        // ── Intentionally NOT seeded here (see DemoSeeder): ─────────
        //   EntitySeeder, RelationshipSeeder, ChronicleSeeder
        // The base seed leaves the knowledge graph empty so the agentic
        // pipeline is the sole author of that content.
    }
}
