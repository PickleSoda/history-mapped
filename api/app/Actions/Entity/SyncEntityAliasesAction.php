<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Models\Entity;
use App\Models\EntityAlias;

/**
 * Make an entity's alias rows match a list of names: rows whose name is not in
 * the list are removed, missing names are added with the given source. Rows
 * that stay keep their language / source / primary flag.
 */
class SyncEntityAliasesAction
{
    /**
     * @param  list<string>  $names
     * @return array{added: int, removed: int}
     */
    public function __invoke(Entity $entity, array $names, string $source): array
    {
        $wanted = array_values(array_unique(array_filter(array_map('trim', $names), fn ($n) => $n !== '')));
        $current = $entity->aliases()->pluck('name')->all();

        $removed = array_values(array_diff($current, $wanted));
        $added = array_values(array_diff($wanted, $current));

        if ($removed !== []) {
            $entity->aliases()->whereIn('name', $removed)->delete();
        }
        foreach ($added as $name) {
            EntityAlias::query()->create([
                'entity_id' => $entity->entity_id,
                'name' => $name,
                'source' => $source,
            ]);
        }

        return ['added' => count($added), 'removed' => count(array_unique($removed))];
    }
}
