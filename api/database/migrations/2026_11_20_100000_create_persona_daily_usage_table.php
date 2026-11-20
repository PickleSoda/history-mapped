<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Messages a user sent to people per UTC day. A counter of its own, not a
 * count of `persona_messages`: clearing a conversation deletes its messages,
 * and must not hand the day's quota back.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('persona_daily_usage', function (Blueprint $table) {
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->date('day');
            $table->unsignedInteger('used')->default(0);

            $table->primary(['user_id', 'day']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('persona_daily_usage');
    }
};
