<?php

declare(strict_types=1);

namespace App\Enums;

/**
 * Where a chronicle_tags / entity_tags row came from. `tags:sync` replaces
 * Curated and Derived rows on every run and never touches Manual ones.
 */
enum TagSource: string
{
    /** Set by an admin, the API, or the pipeline payload. */
    case Manual = 'manual';
    /** From database/data/tags/chronicles.json. */
    case Curated = 'curated';
    /** Computed from dates, entity type, or the chronicles an entity appears in. */
    case Derived = 'derived';
}
