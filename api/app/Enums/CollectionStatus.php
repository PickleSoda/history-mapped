<?php

declare(strict_types=1);

namespace App\Enums;

/** A curated collection is served only when published. */
enum CollectionStatus: string
{
    case Draft = 'draft';
    case Published = 'published';
}
