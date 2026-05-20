<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Models\Entity;
use App\Models\EntityAlias;

class BackfillAliasesAction
{
    public function __invoke(Entity $entity): int
    {
        $aliases = $entity->aliases->pluck('name')->filter(fn ($n) => is_string($n) && trim($n) !== '')->all();

        if ($aliases === []) {
            return 0;
        }

        EntityAlias::query()->where('entity_id', $entity->entity_id)->delete();

        foreach ($aliases as $alias) {
            EntityAlias::query()->create([
                'entity_id' => $entity->entity_id,
                'name' => trim($alias),
                'is_primary' => false,
            ]);
        }

        return EntityAlias::query()->where('entity_id', $entity->entity_id)->count();
    }
}
