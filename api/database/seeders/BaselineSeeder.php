<?php

declare(strict_types=1);

namespace Database\Seeders;

use App\Models\User;
use Illuminate\Database\Seeder;

/**
 * Seeds a "blank-slate" baseline: everything the application needs to run,
 * EXCEPT pipeline-generated content (entities, relationships, chronicles).
 *
 * Use this when you want to evaluate the agentic pipeline from an empty
 * knowledge graph — roles, dev users, and curated reference tables are
 * present, but the entities / relationships / chronicles tables start empty
 * so the pipeline is the sole author of that content.
 *
 * Usage:
 *   php artisan migrate:fresh --seeder=Database\\Seeders\\BaselineSeeder
 *   php artisan db:seed --class=Database\\Seeders\\BaselineSeeder
 *
 * Contrast with {@see DatabaseSeeder}, which additionally seeds the demo
 * EntitySeeder / RelationshipSeeder / ChronicleSeeder fixtures.
 */
class BaselineSeeder extends Seeder
{
    public function run(): void
    {
        // ── Roles must exist before users are assigned them ──────────

        $this->call(RoleSeeder::class);

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

        // ── Intentionally NOT seeded (pipeline is the author): ──────
        //   EntitySeeder, RelationshipSeeder, ChronicleSeeder
        $this->command->info('Baseline seeded: roles, users, reference tables. Entities/relationships/chronicles left EMPTY for the pipeline.');
    }
}
