<?php

declare(strict_types=1);

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;

/**
 * Move every serial/identity sequence in the app schema up to its column's
 * max, so the next insert can't collide with an existing row. It never moves
 * a sequence down.
 *
 *   php artisan db:repair-sequences            # repair (prints what moved)
 *   php artisan db:repair-sequences --dry-run  # report only
 *
 * A data-only pg_dump carries a `setval` for every sequence, including those
 * of tables whose data it excludes (`migrations`, `users`, …). Loading the
 * content dump on the droplet therefore reset those sequences to the local
 * DB's values, and the next `migrate` failed with a `migrations_pkey`
 * duplicate. The prod `migrate` job runs this first, and so does the content
 * loader after a load (docs/implementation-docs/content-data-transfer.md).
 */
class RepairSequencesCommand extends Command
{
    protected $signature = 'db:repair-sequences {--dry-run : Report the sequences that are behind without moving them}';

    protected $description = 'Move sequences that are behind their column max up to it';

    public function handle(): int
    {
        $sequences = DB::select(<<<'SQL'
            SELECT format('%I.%I', sn.nspname, s.relname) AS sequence,
                   format('%I.%I', tn.nspname, t.relname) AS tbl,
                   format('%I', a.attname) AS col,
                   ps.last_value
            FROM pg_class s
            JOIN pg_namespace sn ON sn.oid = s.relnamespace
            JOIN pg_depend d ON d.classid = 'pg_class'::regclass AND d.objid = s.oid
                AND d.refclassid = 'pg_class'::regclass AND d.deptype IN ('a', 'i')
            JOIN pg_class t ON t.oid = d.refobjid
            JOIN pg_namespace tn ON tn.oid = t.relnamespace
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
            JOIN pg_sequences ps ON ps.schemaname = sn.nspname AND ps.sequencename = s.relname
            WHERE s.relkind = 'S' AND sn.nspname = current_schema()
            ORDER BY 1
            SQL);

        $dryRun = (bool) $this->option('dry-run');
        $behind = 0;
        foreach ($sequences as $seq) {
            $max = DB::scalar("SELECT max({$seq->col}) FROM {$seq->tbl}");
            // last_value is null until the sequence's first nextval.
            if ($max === null || ($seq->last_value !== null && (int) $seq->last_value >= (int) $max)) {
                continue;
            }
            $behind++;
            if (! $dryRun) {
                DB::select('SELECT setval(?::regclass, ?, true)', [$seq->sequence, (int) $max]);
            }
            $this->components->twoColumnDetail($seq->sequence, ($seq->last_value ?? 'unused').' → '.$max.($dryRun ? ' (dry run)' : ''));
        }

        $this->components->info($behind === 0
            ? 'All '.count($sequences).' sequences are at or past their column max.'
            : ($dryRun ? "{$behind} sequence(s) are behind." : "Moved {$behind} sequence(s) up to their column max."));

        return self::SUCCESS;
    }
}
