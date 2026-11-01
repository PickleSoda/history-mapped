<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

/**
 * A content load reset sequences below their tables' rows; the repair moves
 * them back up (never down) so the next insert gets a fresh id.
 */
class RepairSequencesCommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_moves_a_sequence_that_is_behind_up_to_the_column_max(): void
    {
        $users = User::factory()->count(3)->create();
        $max = (int) $users->max('id');
        $this->resetUsersSequence();

        $this->artisan('db:repair-sequences')
            ->expectsOutputToContain('users_id_seq')
            ->assertSuccessful();

        $this->assertSame($max, $this->usersSequenceValue());
        $this->assertSame($max + 1, User::factory()->create()->id);
    }

    public function test_a_dry_run_reports_without_moving(): void
    {
        User::factory()->count(2)->create();
        $this->resetUsersSequence();

        $this->artisan('db:repair-sequences', ['--dry-run' => true])
            ->expectsOutputToContain('users_id_seq')
            ->assertSuccessful();

        $this->assertNull($this->usersSequenceValue());
    }

    public function test_it_leaves_a_sequence_ahead_of_its_rows_alone(): void
    {
        $user = User::factory()->create();
        DB::select("SELECT setval(pg_get_serial_sequence('users', 'id'), ?, true)", [$user->id + 100]);

        $this->artisan('db:repair-sequences')->assertSuccessful();

        $this->assertSame($user->id + 100, $this->usersSequenceValue());
    }

    /** What a data-only dump from a DB with no users does: `setval(…, 1, false)`. */
    private function resetUsersSequence(): void
    {
        DB::select("SELECT setval(pg_get_serial_sequence('users', 'id'), 1, false)");
    }

    private function usersSequenceValue(): ?int
    {
        $value = DB::scalar("SELECT last_value FROM pg_sequences WHERE schemaname = current_schema() AND sequencename = 'users_id_seq'");

        return $value === null ? null : (int) $value;
    }
}
