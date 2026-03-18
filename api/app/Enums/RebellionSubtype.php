<?php

declare(strict_types=1);

namespace App\Enums;

enum RebellionSubtype: string
{
    case Revolution = 'revolution';
    case Rebellion = 'rebellion';
    case Coup = 'coup';
    case CivilWar = 'civil_war';
    case PeasantUprising = 'peasant_uprising';
    case SlaveRevolt = 'slave_revolt';
    case MilitaryMutiny = 'military_mutiny';
    case SeparatistMovement = 'separatist_movement';
    case ReligiousUprising = 'religious_uprising';
    case Other = 'other';
}
