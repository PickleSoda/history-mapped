<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Models\Entity;
use Illuminate\Support\Facades\DB;

/**
 * Delete an entity and its dependent relationships.
 *
 * Most dependent tables cascade or null on delete (FK constraint). The
 * chronicle_entry_entities pivot is the sole exception — its entity_id FK
 * uses RESTRICT to protect narrative integrity, so we detach the entity's
 * participant rows first, leaving the chronicle entries (and their other
 * participants) intact. Wrapped in a transaction for atomicity and to allow
 * a future soft-delete migration.
 */
class DeleteEntityAction
{
    public function __invoke(Entity $entity): void
    {
        DB::transaction(function () use ($entity): void {
            DB::table('chronicle_entry_entities')
                ->where('entity_id', $entity->entity_id)
                ->delete();

            $entity->delete();
        });
    }
}
