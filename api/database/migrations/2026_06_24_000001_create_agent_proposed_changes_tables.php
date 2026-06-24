<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('agent_proposed_changes', function (Blueprint $t) {
            $t->uuid('id')->primary();
            $t->foreignId('user_id')->constrained()->cascadeOnDelete();
            $t->string('conversation_id')->nullable();
            $t->string('context_type');           // 'entity' | 'chronicle'
            $t->string('context_id');
            $t->timestamps();
            $t->index(['context_type', 'context_id']);
        });

        Schema::create('agent_proposed_change_parts', function (Blueprint $t) {
            $t->uuid('id')->primary();
            $t->foreignUuid('change_id')->constrained('agent_proposed_changes')->cascadeOnDelete();
            $t->string('key');                    // unique within a change
            $t->string('tool');
            $t->json('payload');
            $t->json('human_diff');
            $t->string('status')->default('pending'); // pending|applied|discarded
            $t->string('depends_on')->nullable();     // another part's key
            $t->string('result_id')->nullable();      // entity/relationship id once applied
            $t->timestamp('applied_at')->nullable();
            $t->timestamps();
            $t->index(['change_id', 'status']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('agent_proposed_change_parts');
        Schema::dropIfExists('agent_proposed_changes');
    }
};
