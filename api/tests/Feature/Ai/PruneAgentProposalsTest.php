<?php

declare(strict_types=1);

namespace Tests\Feature\Ai;

use App\Models\Ai\ProposedChange;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

/**
 * Tests for App\Console\Commands\PruneAgentProposals (ai:prune-proposals).
 *
 * Retention rules
 *   - pending | discarded parts: deleted when created_at < now()-7 days
 *   - applied parts:             deleted when applied_at  < now()-1 year
 *   - orphaned parent changes:   deleted when no parts remain
 *   - conversations:             deleted when updated_at  < now()-90 days
 */
class PruneAgentProposalsTest extends TestCase
{
    use RefreshDatabase;

    // ── helpers ───────────────────────────────────────────────────────────────

    private function makeChange(): ProposedChange
    {
        $user = User::factory()->create();

        return ProposedChange::create([
            'user_id' => $user->id,
            'context_type' => 'entity',
            'context_id' => 'e-test',
        ]);
    }

    private function makePart(ProposedChange $change, array $attrs = []): string
    {
        $id = (string) Str::uuid();

        DB::table('agent_proposed_change_parts')->insert(array_merge([
            'id' => $id,
            'change_id' => $change->id,
            'key' => uniqid('k', true),
            'tool' => 'update_entity_fields',
            'payload' => json_encode(['name' => 'Test']),
            'human_diff' => json_encode(['summary' => 'Test']),
            'status' => 'pending',
            'applied_at' => null,
            'created_at' => now(),
            'updated_at' => now(),
        ], $attrs));

        return $id;
    }

    private function conversationsTable(): string
    {
        return config('ai.conversations.tables.conversations', 'agent_conversations');
    }

    private function messagesTable(): string
    {
        return config('ai.conversations.tables.messages', 'agent_conversation_messages');
    }

    private function makeConversation(array $attrs = []): string
    {
        $id = (string) Str::uuid();

        DB::table($this->conversationsTable())->insert(array_merge([
            'id' => $id,
            'user_id' => null,
            'title' => 'Test conversation',
            'created_at' => now(),
            'updated_at' => now(),
        ], $attrs));

        return $id;
    }

    private function makeMessage(string $conversationId, array $attrs = []): string
    {
        $id = (string) Str::uuid();

        DB::table($this->messagesTable())->insert(array_merge([
            'id' => $id,
            'conversation_id' => $conversationId,
            'user_id' => null,
            'agent' => 'entity-editor',
            'role' => 'user',
            'content' => 'Test message',
            'attachments' => '[]',
            'tool_calls' => '[]',
            'tool_results' => '[]',
            'usage' => '{}',
            'meta' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ], $attrs));

        return $id;
    }

    // ── pending / discarded parts ─────────────────────────────────────────────

    public function test_old_pending_part_is_deleted(): void
    {
        $change = $this->makeChange();
        $old8days = Carbon::now()->subDays(8)->toDateTimeString();
        $oldPartId = $this->makePart($change, ['status' => 'pending', 'created_at' => $old8days, 'updated_at' => $old8days]);

        $this->artisan('ai:prune-proposals')->assertSuccessful();

        $this->assertDatabaseMissing('agent_proposed_change_parts', ['id' => $oldPartId]);
    }

    public function test_old_discarded_part_is_deleted(): void
    {
        $change = $this->makeChange();
        $old8days = Carbon::now()->subDays(8)->toDateTimeString();
        $oldPartId = $this->makePart($change, ['status' => 'discarded', 'created_at' => $old8days, 'updated_at' => $old8days]);

        $this->artisan('ai:prune-proposals')->assertSuccessful();

        $this->assertDatabaseMissing('agent_proposed_change_parts', ['id' => $oldPartId]);
    }

    public function test_recent_pending_part_is_kept(): void
    {
        $change = $this->makeChange();
        $recentPartId = $this->makePart($change, ['status' => 'pending']);

        $this->artisan('ai:prune-proposals')->assertSuccessful();

        $this->assertDatabaseHas('agent_proposed_change_parts', ['id' => $recentPartId]);
    }

    // ── applied parts ─────────────────────────────────────────────────────────

    public function test_applied_part_older_than_one_year_is_deleted(): void
    {
        $change = $this->makeChange();
        $appliedAt = Carbon::now()->subYear()->subDay()->toDateTimeString();
        $oldAppliedId = $this->makePart($change, [
            'status' => 'applied',
            'applied_at' => $appliedAt,
        ]);

        $this->artisan('ai:prune-proposals')->assertSuccessful();

        $this->assertDatabaseMissing('agent_proposed_change_parts', ['id' => $oldAppliedId]);
    }

    public function test_recently_applied_part_is_kept(): void
    {
        $change = $this->makeChange();
        $recentAppliedId = $this->makePart($change, [
            'status' => 'applied',
            'applied_at' => Carbon::now()->subMonths(6)->toDateTimeString(),
        ]);

        $this->artisan('ai:prune-proposals')->assertSuccessful();

        $this->assertDatabaseHas('agent_proposed_change_parts', ['id' => $recentAppliedId]);
    }

    public function test_applied_part_with_old_created_at_but_recent_applied_at_is_kept(): void
    {
        // Rule 1 only targets pending|discarded — status=applied is exempt.
        // Rule 2 checks applied_at, not created_at; 3 months ago is well within 1 year.
        $change = $this->makeChange();
        $partId = $this->makePart($change, [
            'status' => 'applied',
            'created_at' => Carbon::now()->subDays(400)->toDateTimeString(),
            'applied_at' => Carbon::now()->subMonths(3)->toDateTimeString(),
        ]);

        $this->artisan('ai:prune-proposals')->assertSuccessful();

        $this->assertDatabaseHas('agent_proposed_change_parts', ['id' => $partId]);
    }

    // ── orphaned parent changes ───────────────────────────────────────────────

    public function test_orphaned_change_is_deleted_after_all_parts_pruned(): void
    {
        $change = $this->makeChange();
        $changeId = $change->id;

        // Only one old pending part — will be pruned, leaving no children.
        $old8days = Carbon::now()->subDays(8)->toDateTimeString();
        $this->makePart($change, ['status' => 'pending', 'created_at' => $old8days, 'updated_at' => $old8days]);

        $this->artisan('ai:prune-proposals')->assertSuccessful();

        $this->assertDatabaseMissing('agent_proposed_changes', ['id' => $changeId]);
    }

    public function test_change_with_remaining_parts_is_kept(): void
    {
        $change = $this->makeChange();
        $changeId = $change->id;

        // One old pending (will be deleted) + one recent pending (kept).
        $old8days = Carbon::now()->subDays(8)->toDateTimeString();
        $this->makePart($change, ['status' => 'pending', 'created_at' => $old8days, 'updated_at' => $old8days]);
        $this->makePart($change, ['status' => 'pending']);

        $this->artisan('ai:prune-proposals')->assertSuccessful();

        // Parent change must survive because the recent part was kept.
        $this->assertDatabaseHas('agent_proposed_changes', ['id' => $changeId]);
    }

    // ── conversations ─────────────────────────────────────────────────────────

    public function test_old_conversation_is_deleted(): void
    {
        $oldUpdatedAt = Carbon::now()->subDays(91)->toDateTimeString();
        $oldConvId = $this->makeConversation(['updated_at' => $oldUpdatedAt, 'created_at' => $oldUpdatedAt]);

        $this->artisan('ai:prune-proposals')->assertSuccessful();

        $this->assertDatabaseMissing($this->conversationsTable(), ['id' => $oldConvId]);
    }

    public function test_old_conversation_also_removes_its_messages(): void
    {
        $oldUpdatedAt = Carbon::now()->subDays(91)->toDateTimeString();
        $oldConvId = $this->makeConversation(['updated_at' => $oldUpdatedAt, 'created_at' => $oldUpdatedAt]);
        $msgId = $this->makeMessage($oldConvId);

        $this->artisan('ai:prune-proposals')->assertSuccessful();

        $this->assertDatabaseMissing($this->conversationsTable(), ['id' => $oldConvId]);
        $this->assertDatabaseMissing($this->messagesTable(), ['id' => $msgId]);
    }

    public function test_recent_conversation_messages_are_not_deleted(): void
    {
        $recentConvId = $this->makeConversation();
        $msgId = $this->makeMessage($recentConvId);

        $this->artisan('ai:prune-proposals')->assertSuccessful();

        $this->assertDatabaseHas($this->conversationsTable(), ['id' => $recentConvId]);
        $this->assertDatabaseHas($this->messagesTable(), ['id' => $msgId]);
    }

    public function test_recent_conversation_is_kept(): void
    {
        $recentConvId = $this->makeConversation();

        $this->artisan('ai:prune-proposals')->assertSuccessful();

        $this->assertDatabaseHas($this->conversationsTable(), ['id' => $recentConvId]);
    }

    // ── dry-run ───────────────────────────────────────────────────────────────

    public function test_dry_run_does_not_delete_any_rows_but_reports_counts(): void
    {
        $change = $this->makeChange();

        $old8days = Carbon::now()->subDays(8)->toDateTimeString();
        $oldPartId = $this->makePart($change, ['status' => 'pending', 'created_at' => $old8days, 'updated_at' => $old8days]);

        $oldConvUpdated = Carbon::now()->subDays(91)->toDateTimeString();
        $oldConvId = $this->makeConversation(['updated_at' => $oldConvUpdated, 'created_at' => $oldConvUpdated]);

        $this->artisan('ai:prune-proposals', ['--dry-run' => true])
            ->assertSuccessful()
            ->expectsOutputToContain('DRY-RUN')
            // Reported counts must be non-zero so a silently-zero bug is caught.
            ->expectsOutputToContain('1');

        // Nothing was actually deleted.
        $this->assertDatabaseHas('agent_proposed_change_parts', ['id' => $oldPartId]);
        $this->assertDatabaseHas($this->conversationsTable(), ['id' => $oldConvId]);
    }

    public function test_dry_run_orphan_count_reflects_would_be_deletions(): void
    {
        // Change A: one old pending part → would become orphaned after prune.
        $changeA = $this->makeChange();
        $old8days = Carbon::now()->subDays(8)->toDateTimeString();
        $this->makePart($changeA, ['status' => 'pending', 'created_at' => $old8days, 'updated_at' => $old8days]);

        // Change B: one recent pending part → would NOT be pruned, change survives.
        $changeB = $this->makeChange();
        $this->makePart($changeB, ['status' => 'pending']);

        // Dry-run should report orphaned=1 (only change A).
        $this->artisan('ai:prune-proposals', ['--dry-run' => true])
            ->assertSuccessful()
            ->expectsOutputToContain('DRY-RUN');

        // Neither change should be deleted in dry-run.
        $this->assertDatabaseHas('agent_proposed_changes', ['id' => $changeA->id]);
        $this->assertDatabaseHas('agent_proposed_changes', ['id' => $changeB->id]);
        // The old part should still exist too.
        $this->assertDatabaseHas('agent_proposed_change_parts', ['change_id' => $changeA->id]);
    }
}
