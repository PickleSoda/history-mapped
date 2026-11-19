<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Contributions grow a second kind: `create` proposals (a new entity or a new
 * relationship, held as a validated payload) alongside the original `edit`
 * rows (one prose field). Proposals can also arrive through the MCP connector,
 * so the row records its `source` and the connecting `client`.
 *
 * For a `create` row `target_type` says what is proposed (entity or
 * relationship), `target_id` stays null until approval and then holds the id of
 * the record that was created, and the field/base/proposed/diff columns are empty.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('contributions', function (Blueprint $t) {
            $t->string('kind', 16)->default('edit')->after('user_id');
            $t->jsonb('payload')->nullable()->after('diff');
            $t->string('source', 16)->default('atlas')->after('payload');
            $t->string('client', 255)->nullable()->after('source');

            $t->string('target_id')->nullable()->change();
            $t->string('field', 64)->nullable()->change();
            $t->text('base_text')->nullable()->change();
            $t->text('proposed_text')->nullable()->change();
            $t->jsonb('diff')->nullable()->change();

            $t->index(['kind', 'status']);
        });
    }

    public function down(): void
    {
        Schema::table('contributions', function (Blueprint $t) {
            $t->dropIndex(['kind', 'status']);
        });

        // Create proposals have no edit-shaped columns, so they cannot be kept.
        DB::table('contributions')->where('kind', 'create')->delete();

        Schema::table('contributions', function (Blueprint $t) {
            $t->string('target_id')->nullable(false)->change();
            $t->string('field', 64)->nullable(false)->change();
            $t->text('base_text')->nullable(false)->change();
            $t->text('proposed_text')->nullable(false)->change();
            $t->jsonb('diff')->nullable(false)->change();
            $t->dropColumn(['kind', 'payload', 'source', 'client']);
        });
    }
};
