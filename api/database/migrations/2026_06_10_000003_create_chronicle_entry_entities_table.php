<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('chronicle_entry_entities', function (Blueprint $table) {
            $table->uuid('entry_id');
            $table->uuid('entity_id');
            $table->string('role', 16)->default('participant');
            $table->integer('sequence_in_entry')->nullable();

            $table->primary(['entry_id', 'entity_id']);

            $table->foreign('entry_id')
                ->references('entry_id')
                ->on('chronicle_entries')
                ->cascadeOnDelete();

            $table->foreign('entity_id')
                ->references('entity_id')
                ->on('entities')
                ->restrictOnDelete();

            $table->index(['entry_id', 'role']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('chronicle_entry_entities');
    }
};
