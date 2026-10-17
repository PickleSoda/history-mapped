<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Personal saved items: a user stars entities / chronicles / relationships and
 * may file each star in any number of their folders. Targets are referenced
 * by (type, id) without a foreign key so a star survives a content reload;
 * a dangling star renders as "no longer available".
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('stars', function (Blueprint $t) {
            $t->id();
            $t->foreignId('user_id')->constrained()->cascadeOnDelete();
            $t->string('starrable_type', 32);     // SaveableType value
            $t->string('starrable_id');
            $t->timestamps();
            $t->unique(['user_id', 'starrable_type', 'starrable_id']);
            $t->index(['user_id', 'created_at']);
        });

        Schema::create('saved_folders', function (Blueprint $t) {
            $t->id();
            $t->foreignId('user_id')->constrained()->cascadeOnDelete();
            $t->string('name', 80);
            $t->string('description', 500)->nullable();
            $t->string('color', 7)->nullable();    // #rrggbb
            $t->timestamps();
            $t->unique(['user_id', 'name']);
        });

        Schema::create('saved_folder_star', function (Blueprint $t) {
            $t->foreignId('saved_folder_id')->constrained()->cascadeOnDelete();
            $t->foreignId('star_id')->constrained()->cascadeOnDelete();
            $t->timestamp('created_at')->useCurrent();
            $t->primary(['saved_folder_id', 'star_id']);
            $t->index('star_id');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('saved_folder_star');
        Schema::dropIfExists('saved_folders');
        Schema::dropIfExists('stars');
    }
};
