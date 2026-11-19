<?php

declare(strict_types=1);

namespace App\Exceptions;

use RuntimeException;

/**
 * A proposed entity looks like entities the atlas already has (same name, same
 * type, close in time). Nothing is recorded until the caller confirms.
 */
class PossibleDuplicatesException extends RuntimeException
{
    /** @param  list<array{entity_id: string, name: string, entity_type: string, start_year: int|null, end_year: int|null}>  $duplicates */
    public function __construct(public readonly array $duplicates)
    {
        parent::__construct('The atlas already has entities with this name and type around the same time.');
    }
}
