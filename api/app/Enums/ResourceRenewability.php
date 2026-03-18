<?php

declare(strict_types=1);

namespace App\Enums;

enum ResourceRenewability: string
{
    case Renewable = 'renewable';
    case Finite = 'finite';
    case Cyclical = 'cyclical';
    case Unknown = 'unknown';
}
