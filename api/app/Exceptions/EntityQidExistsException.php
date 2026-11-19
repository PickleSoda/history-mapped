<?php

declare(strict_types=1);

namespace App\Exceptions;

use App\Models\Entity;
use RuntimeException;

/** A proposed entity's Wikidata QID is already an entity in the atlas. */
class EntityQidExistsException extends RuntimeException
{
    public function __construct(public readonly Entity $entity)
    {
        parent::__construct("The atlas already has {$entity->wikidata_id}: {$entity->name}.");
    }
}
