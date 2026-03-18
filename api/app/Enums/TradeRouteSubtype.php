<?php

declare(strict_types=1);

namespace App\Enums;

enum TradeRouteSubtype: string
{
    case Overland = 'overland';
    case Maritime = 'maritime';
    case Riverine = 'riverine';
    case Mixed = 'mixed';
    case Pilgrimage = 'pilgrimage';
    case MilitarySupply = 'military_supply';
    case Other = 'other';
}
