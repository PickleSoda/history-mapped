<?php

declare(strict_types=1);

namespace Database\Seeders;

use Illuminate\Database\Seeder;

/**
 * Full demo dataset: the minimal base ({@see DatabaseSeeder}) PLUS the curated
 * entity / relationship / chronicle fixtures.
 *
 * Use this when you want a populated knowledge graph to click around in (local
 * dev, demos, UI work) rather than the blank slate the pipeline writes into.
 *
 * Usage (run against a fresh database):
 *   php artisan db:seed --class=Database\\Seeders\\DemoSeeder
 *   php artisan migrate:fresh --seeder=Database\\Seeders\\DemoSeeder
 *
 * Contrast with {@see DatabaseSeeder} (the default), which seeds only roles,
 * permissions, dev users, and reference tables.
 */
class DemoSeeder extends Seeder
{
    public function run(): void
    {
        // ── Minimal base: roles, permissions, dev users, reference data ──

        $this->call(DatabaseSeeder::class);

        // ── Demo content (entities, relationships, chronicles) ──────────

        $this->call(EntitySeeder::class);
        $this->call(RelationshipSeeder::class);
        $this->call(ChronicleSeeder::class);

        $this->command->info('Demo seeded: base + entities/relationships/chronicles fixtures.');
    }
}
