<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Index `chronicle_entries.primary_relationship_id`.
 *
 * GET /discover/for-you asks which chronicle entries are built on a seed's
 * relationships. Without an index that is a scan of every entry (26k rows,
 * 14 ms locally, on every request); with it, a few index lookups. The column
 * is also a foreign key, so deleting a relationship scanned the table too.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('chronicle_entries', function (Blueprint $table): void {
            $table->index('primary_relationship_id');
        });
    }

    public function down(): void
    {
        Schema::table('chronicle_entries', function (Blueprint $table): void {
            $table->dropIndex(['primary_relationship_id']);
        });
    }
};
