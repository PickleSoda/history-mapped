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
        Schema::create('chronicles', function (Blueprint $table) {
            $table->uuid('chronicle_id')->primary()->default(DB::raw('gen_random_uuid()'));
            $table->text('title');
            $table->text('slug')->unique();
            $table->string('source_type', 32);
            $table->text('source_reference')->nullable();
            $table->string('status', 16)->default('draft');
            $table->jsonb('metadata')->default('{}');
            $table->text('created_by')->nullable();
            $table->timestamps();

            $table->index('status');
            $table->index('source_type');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('chronicles');
    }
};
