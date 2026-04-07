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
        Schema::create('entity_aliases', function (Blueprint $table) {
            $table->uuid('alias_id')->primary()->default(DB::raw('gen_random_uuid()'));
            $table->uuid('entity_id');
            $table->text('name');
            $table->text('language')->nullable();
            $table->text('source')->nullable();
            $table->boolean('is_primary')->default(false);
            $table->timestamps();

            $table->foreign('entity_id')
                ->references('entity_id')
                ->on('entities')
                ->cascadeOnDelete();
        });

        DB::statement('CREATE INDEX ea_entity_idx ON entity_aliases (entity_id)');
        DB::statement('CREATE INDEX ea_name_idx ON entity_aliases (name)');
    }

    public function down(): void
    {
        Schema::dropIfExists('entity_aliases');
    }
};
