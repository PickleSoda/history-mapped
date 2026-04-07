<?php

declare(strict_types=1);

namespace App\Actions\EntityModelV2;

use App\Models\Entity;
use App\Models\EntityAlias;

class BackfillAliasesAction
{
    public function __invoke(Entity $entity): int
    {
        $aliases = $entity->alternative_names;

        if (! is_array($aliases) || $aliases === []) {
            return 0;
        }

        EntityAlias::query()->where('entity_id', $entity->entity_id)->delete();

        foreach ($aliases as $alias) {
            if (! is_string($alias) || trim($alias) === '') {
                continue;
            }

            EntityAlias::query()->create([
                'entity_id' => $entity->entity_id,
                'name' => trim($alias),
                'is_primary' => false,
            ]);
        }

        return EntityAlias::query()->where('entity_id', $entity->entity_id)->count();
    }
}
