<?php

declare(strict_types=1);

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;

class PruneAgentProposals extends Command
{
    protected $signature = 'ai:prune-proposals
                            {--dry-run : Report row counts without deleting anything}';

    protected $description = 'Prune stale AI agent proposals, parts, and chat conversations';

    public function handle(): int
    {
        $dryRun = (bool) $this->option('dry-run');
        $mode = $dryRun ? 'DRY-RUN' : 'APPLIED';

        // ── Rule 1: pending|discarded parts older than 7 days ────────────────
        $cutoffShort = Carbon::now()->subDays(7);

        $stalePendingOrDiscardedParts = DB::table('agent_proposed_change_parts')
            ->whereIn('status', ['pending', 'discarded'])
            ->where('created_at', '<', $cutoffShort);

        $countStaleParts = $stalePendingOrDiscardedParts->count();

        if (! $dryRun) {
            $stalePendingOrDiscardedParts->delete();
        }

        // ── Rule 2: applied parts older than 1 year ───────────────────────────
        $cutoffLong = Carbon::now()->subYear();

        $oldAppliedParts = DB::table('agent_proposed_change_parts')
            ->where('status', 'applied')
            ->where('applied_at', '<', $cutoffLong);

        $countOldApplied = $oldAppliedParts->count();

        if (! $dryRun) {
            $oldAppliedParts->delete();
        }

        // ── Rule 3: orphaned parent changes (no remaining parts) ──────────────
        $orphanedChanges = DB::table('agent_proposed_changes')
            ->whereNotExists(function ($q) {
                $q->select(DB::raw(1))
                    ->from('agent_proposed_change_parts')
                    ->whereColumn('agent_proposed_change_parts.change_id', 'agent_proposed_changes.id');
            });

        $countOrphanedChanges = $orphanedChanges->count();

        if (! $dryRun) {
            $orphanedChanges->delete();
        }

        // ── Rule 4: conversations older than 90 days ──────────────────────────
        $conversationsTable = config('ai.conversations.tables.conversations', 'agent_conversations');
        $cutoffConversations = Carbon::now()->subDays(90);

        $oldConversations = DB::table($conversationsTable)
            ->where('updated_at', '<', $cutoffConversations);

        $countOldConversations = $oldConversations->count();

        if (! $dryRun) {
            $oldConversations->delete();
        }

        // ── Summary ───────────────────────────────────────────────────────────
        $this->info("[{$mode}] ai:prune-proposals summary");
        $this->table(['rule', 'rows'], [
            ['pending/discarded parts > 7 days', (string) $countStaleParts],
            ['applied parts > 1 year', (string) $countOldApplied],
            ['orphaned parent changes', (string) $countOrphanedChanges],
            ["conversations ({$conversationsTable}) > 90 days", (string) $countOldConversations],
        ]);

        return self::SUCCESS;
    }
}
