<?php

declare(strict_types=1);

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;

class PruneAgentProposalsCommand extends Command
{
    protected $signature = 'ai:prune-proposals
                            {--dry-run : Report row counts without deleting anything}';

    protected $description = 'Prune stale AI agent proposals, parts, and chat conversations';

    public function handle(): int
    {
        $dryRun = (bool) $this->option('dry-run');
        $mode = $dryRun ? 'DRY-RUN' : 'APPLIED';

        $conversationsTable = config('ai.conversations.tables.conversations', 'agent_conversations');
        $messagesTable = config('ai.conversations.tables.messages', 'agent_conversation_messages');

        // ── Rule 1: pending|discarded parts older than 7 days ────────────────
        $cutoffShort = Carbon::now()->subDays(7);

        $stalePendingOrDiscardedParts = DB::table('agent_proposed_change_parts')
            ->whereIn('status', ['pending', 'discarded'])
            ->where('created_at', '<', $cutoffShort);

        $countStaleParts = $dryRun
            ? $stalePendingOrDiscardedParts->count()
            : $stalePendingOrDiscardedParts->delete();

        // ── Rule 2: applied parts older than 1 year ───────────────────────────
        $cutoffLong = Carbon::now()->subYear();

        $oldAppliedParts = DB::table('agent_proposed_change_parts')
            ->where('status', 'applied')
            ->where('applied_at', '<', $cutoffLong);

        $countOldApplied = $dryRun
            ? $oldAppliedParts->count()
            : $oldAppliedParts->delete();

        // ── Rule 3: orphaned parent changes (no remaining parts) ──────────────
        // In dry-run, compute would-be-orphaned count BEFORE any actual deletes:
        // a change is orphaned when no part would survive both Rule 1 and Rule 2.
        // A part survives iff it is NOT caught by Rule 1 AND NOT caught by Rule 2.
        if ($dryRun) {
            $countOrphanedChanges = DB::table('agent_proposed_changes')
                ->whereNotExists(function ($q) use ($cutoffShort, $cutoffLong) {
                    $q->select(DB::raw(1))
                        ->from('agent_proposed_change_parts as p')
                        ->whereColumn('p.change_id', 'agent_proposed_changes.id')
                        // Survives Rule 1: NOT (pending|discarded AND created_at < cutoffShort)
                        ->where(function ($r1) use ($cutoffShort) {
                            $r1->whereNotIn('p.status', ['pending', 'discarded'])
                                ->orWhere('p.created_at', '>=', $cutoffShort);
                        })
                        // Survives Rule 2: NOT (applied AND applied_at < cutoffLong)
                        ->where(function ($r2) use ($cutoffLong) {
                            $r2->where('p.status', '!=', 'applied')
                                ->orWhere('p.applied_at', '>=', $cutoffLong)
                                ->orWhereNull('p.applied_at');
                        });
                })
                ->count();
        } else {
            $orphanedChanges = DB::table('agent_proposed_changes')
                ->whereNotExists(function ($q) {
                    $q->select(DB::raw(1))
                        ->from('agent_proposed_change_parts')
                        ->whereColumn('agent_proposed_change_parts.change_id', 'agent_proposed_changes.id');
                });

            $countOrphanedChanges = $orphanedChanges->delete();
        }

        // ── Rule 4: conversations older than 90 days ──────────────────────────
        $cutoffConversations = Carbon::now()->subDays(90);

        if ($dryRun) {
            $countMessagesDeleted = DB::table($messagesTable)
                ->whereIn('conversation_id', fn ($q) => $q->select('id')->from($conversationsTable)->where('updated_at', '<', $cutoffConversations))
                ->count();

            $countOldConversations = DB::table($conversationsTable)
                ->where('updated_at', '<', $cutoffConversations)
                ->count();
        } else {
            // Delete messages via subquery first (no FK cascade on conversation_id).
            $countMessagesDeleted = DB::table($messagesTable)
                ->whereIn('conversation_id', fn ($q) => $q->select('id')->from($conversationsTable)->where('updated_at', '<', $cutoffConversations))
                ->delete();

            $countOldConversations = DB::table($conversationsTable)
                ->where('updated_at', '<', $cutoffConversations)
                ->delete();
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
