<?php

declare(strict_types=1);

namespace App\Support\ContentBundle;

/**
 * Export profile. Public drops internal data (`_`-prefixed attributes and geo-ref source_meta).
 */
enum Profile: string
{
    case Full = 'full';
    case Public = 'public';
}
