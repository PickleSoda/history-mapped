<?php

declare(strict_types=1);

namespace App\Actions\Chronicle;

use App\Models\Chronicle;
use Illuminate\Support\Facades\DB;

class DeleteChronicleAction
{
    /**
     * Delete a chronicle and its entries.
     *
     * Entries are deleted via cascade foreign key; this is a safety net
     * in case cascade is not configured at DB level.
     */
    public function __invoke(Chronicle $chronicle): void
    {
        DB::transaction(function () use ($chronicle): void {
            // Explicitly delete entries if no cascade constraint exists
            $chronicle->entries()->delete();

            $chronicle->delete();
        });
    }
}
