<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('agent_proposed_change_parts', function (Blueprint $table) {
            $table->index('applied_at');
        });

        $conversationsTable = config('ai.conversations.tables.conversations', 'agent_conversations');

        Schema::table($conversationsTable, function (Blueprint $table) {
            $table->index('updated_at');
        });
    }

    public function down(): void
    {
        Schema::table('agent_proposed_change_parts', function (Blueprint $table) {
            $table->dropIndex(['applied_at']);
        });

        $conversationsTable = config('ai.conversations.tables.conversations', 'agent_conversations');

        Schema::table($conversationsTable, function (Blueprint $table) {
            $table->dropIndex(['updated_at']);
        });
    }
};
