<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('chronicle_entries', function (Blueprint $table) {
            $table->uuid('entry_id')->primary()->default(DB::raw('gen_random_uuid()'));
            $table->uuid('chronicle_id');
            $table->integer('sequence_order')->default(0);
            $table->uuid('primary_relationship_id')->nullable();
            $table->text('narrative_text');
            $table->text('notes')->nullable();
            $table->text('source_evidence')->nullable();
            $table->text('generated_by')->nullable();
            $table->timestamps();

            $table->foreign('chronicle_id')
                ->references('chronicle_id')
                ->on('chronicles')
                ->cascadeOnDelete();

            $table->foreign('primary_relationship_id')
                ->references('relationship_id')
                ->on('relationships')
                ->nullOnDelete();

            $table->index(['chronicle_id', 'sequence_order']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('chronicle_entries');
    }
};
