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
        Schema::create('entity_tags', function (Blueprint $table) {
            $table->uuid('entity_tag_id')->primary()->default(DB::raw('gen_random_uuid()'));
            $table->uuid('entity_id');
            $table->text('tag');
            $table->timestamps();

            $table->foreign('entity_id')
                ->references('entity_id')
                ->on('entities')
                ->cascadeOnDelete();
        });

        DB::statement('CREATE INDEX et_entity_idx ON entity_tags (entity_id)');
        DB::statement('CREATE INDEX et_tag_idx ON entity_tags (tag)');
        DB::statement('CREATE UNIQUE INDEX et_entity_tag_unique ON entity_tags (entity_id, tag)');
    }

    public function down(): void
    {
        Schema::dropIfExists('entity_tags');
    }
};
