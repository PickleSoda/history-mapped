<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * "Talk with people": one generated persona per speaker, one conversation per
 * user per speaker, and its messages. The speaker is an entity today (a
 * person); `entity_personas` is keyed by entity so a later city or family
 * speaker is another entity type with its own persona.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('entity_personas', function (Blueprint $table) {
            $table->id();
            $table->foreignUuid('entity_id')->unique()->constrained('entities', 'entity_id')->cascadeOnDelete();
            $table->jsonb('persona');
            $table->integer('knowledge_year');
            $table->string('model', 120)->nullable();
            $table->unsignedSmallInteger('version')->default(1);
            $table->string('source', 16)->default('generated'); // generated | edited
            $table->timestamps();
        });

        Schema::create('persona_conversations', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->foreignUuid('entity_id')->constrained('entities', 'entity_id')->cascadeOnDelete();
            $table->timestamp('last_message_at')->nullable();
            $table->text('summary')->nullable();
            $table->unsignedBigInteger('summarised_until_id')->default(0);
            $table->timestamps();

            $table->unique(['user_id', 'entity_id']);
            $table->index(['user_id', 'last_message_at']);
        });

        Schema::create('persona_messages', function (Blueprint $table) {
            $table->id();
            $table->foreignId('conversation_id')->constrained('persona_conversations')->cascadeOnDelete();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->string('role', 12); // user | assistant
            $table->text('content');
            $table->string('model', 120)->nullable();
            $table->unsignedInteger('prompt_tokens')->nullable();
            $table->unsignedInteger('completion_tokens')->nullable();
            $table->timestamp('created_at')->useCurrent();

            $table->index(['conversation_id', 'id']);
            // The daily cap counts a user's own messages since midnight.
            $table->index(['user_id', 'role', 'created_at']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('persona_messages');
        Schema::dropIfExists('persona_conversations');
        Schema::dropIfExists('entity_personas');
    }
};
