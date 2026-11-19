<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * A narrow copy of entities.name for search. The capped match count of a fuzzy
 * search rechecks every trigram candidate against the row it came from (52,877
 * for "temple of"). Rechecked against the wide `entities` heap that reads 24k
 * blocks; against this table (a uuid and a name, about 40 MB) it reads a few
 * thousand.
 *
 * The copy is kept by a trigger, not by Eloquent: bulk importers write
 * entities with raw SQL and COPY.
 *
 * Safe on a live site: the table and trigger are created first (new writes
 * are mirrored from then on), the backfill is one INSERT ... ON CONFLICT DO
 * NOTHING that takes no lock on entities beyond row share, and the indexes
 * are built CONCURRENTLY, so no write waits for more than the instant the
 * trigger is attached. Every step is repeatable after a failed deploy.
 */
return new class extends Migration
{
    public $withinTransaction = false;

    public function up(): void
    {
        DB::statement('CREATE EXTENSION IF NOT EXISTS pg_trgm');

        DB::statement(<<<'SQL'
            CREATE TABLE IF NOT EXISTS entity_names (
                entity_id uuid PRIMARY KEY REFERENCES entities (entity_id) ON DELETE CASCADE,
                name text NOT NULL
            )
        SQL);

        DB::statement(<<<'SQL'
            CREATE OR REPLACE FUNCTION entity_names_sync() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                INSERT INTO entity_names (entity_id, name)
                VALUES (NEW.entity_id, NEW.name)
                ON CONFLICT (entity_id) DO UPDATE SET name = EXCLUDED.name;
                RETURN NULL;
            END
            $$
        SQL);

        // Deletes cascade through the foreign key. A bulk update that sets the
        // name column to the value it already has (importers do) is skipped.
        DB::statement('DROP TRIGGER IF EXISTS entity_names_sync_trg ON entities');
        DB::statement('DROP TRIGGER IF EXISTS entity_names_insert_trg ON entities');
        DB::statement('DROP TRIGGER IF EXISTS entity_names_update_trg ON entities');
        DB::statement(<<<'SQL'
            CREATE TRIGGER entity_names_insert_trg
            AFTER INSERT ON entities
            FOR EACH ROW EXECUTE FUNCTION entity_names_sync()
        SQL);
        DB::statement(<<<'SQL'
            CREATE TRIGGER entity_names_update_trg
            AFTER UPDATE OF name ON entities
            FOR EACH ROW WHEN (OLD.name IS DISTINCT FROM NEW.name)
            EXECUTE FUNCTION entity_names_sync()
        SQL);

        DB::statement(<<<'SQL'
            INSERT INTO entity_names (entity_id, name)
            SELECT entity_id, name FROM entities
            ON CONFLICT (entity_id) DO NOTHING
        SQL);
        // A name edited while the backfill ran was mirrored by the trigger; the
        // backfill never overwrites it, so settle any row that differs.
        DB::statement(<<<'SQL'
            UPDATE entity_names n SET name = e.name
            FROM entities e
            WHERE e.entity_id = n.entity_id AND e.name IS DISTINCT FROM n.name
        SQL);

        $this->buildIndex('entity_names_name_trgm_idx', 'USING gin (name gin_trgm_ops)');
        $this->buildIndex('entity_names_name_search_idx', "USING gin (to_tsvector('english', name))");
        DB::statement('ANALYZE entity_names');
    }

    public function down(): void
    {
        DB::statement('DROP TRIGGER IF EXISTS entity_names_insert_trg ON entities');
        DB::statement('DROP TRIGGER IF EXISTS entity_names_update_trg ON entities');
        DB::statement('DROP FUNCTION IF EXISTS entity_names_sync()');
        DB::statement('DROP TABLE IF EXISTS entity_names');
    }

    /** A failed CONCURRENTLY build leaves an invalid index that IF NOT EXISTS would keep. */
    private function buildIndex(string $name, string $definition): void
    {
        $invalid = DB::selectOne(
            'SELECT 1 AS found FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid WHERE c.relname = ? AND NOT i.indisvalid',
            [$name],
        );
        if ($invalid !== null) {
            DB::statement("DROP INDEX CONCURRENTLY IF EXISTS {$name}");
        }
        DB::statement("CREATE INDEX CONCURRENTLY IF NOT EXISTS {$name} ON entity_names {$definition}");
    }
};
