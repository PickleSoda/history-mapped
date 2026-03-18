<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Models\Entity;
use Illuminate\Support\Facades\DB;

/**
 * Delete an entity and its dependent relationships.
 *
 * Relationships cascade on delete (FK constraint), but we wrap in a
 * transaction for safety and to allow future soft-delete migration.
 */
class DeleteEntityAction
{
    public function __invoke(Entity $entity): void
    {
        DB::transaction(function () use ($entity): void {
            $entity->delete();
        });
    }
}
