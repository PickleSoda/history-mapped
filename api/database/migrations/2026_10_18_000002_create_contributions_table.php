<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * User-submitted text corrections, held for staff review. Each row snapshots
 * the field as the contributor saw it (`base_text`) next to the proposal and
 * the word-level diff between them (see App\Support\TextDiff).
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('contributions', function (Blueprint $t) {
            $t->id();
            $t->foreignId('user_id')->nullable()->constrained()->nullOnDelete();
            $t->string('target_type', 32);         // ContributionTargetType value
            $t->string('target_id');
            $t->string('field', 64);
            $t->text('base_text');
            $t->text('proposed_text');
            $t->jsonb('diff');
            $t->text('note')->nullable();
            $t->string('status', 16)->default('pending');
            $t->foreignId('reviewer_id')->nullable()->constrained('users')->nullOnDelete();
            $t->text('review_note')->nullable();
            $t->timestamp('reviewed_at')->nullable();
            $t->timestamps();

            $t->index(['status', 'created_at']);
            $t->index(['target_type', 'target_id', 'field']);
            $t->index(['user_id', 'created_at']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('contributions');
    }
};
