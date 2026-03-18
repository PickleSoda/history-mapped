<?php

declare(strict_types=1);

namespace App\Enums;

enum EntityGroup: string
{
    case Polity = 'POLITY';
    case Place = 'PLACE';
    case Event = 'EVENT';
    case Economy = 'ECONOMY';
    case Culture = 'CULTURE';
}
