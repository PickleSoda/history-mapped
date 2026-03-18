<?php

declare(strict_types=1);

namespace App\Enums;

enum MilitaryComposition: string
{
    case Professional = 'professional';
    case Conscript = 'conscript';
    case Mercenary = 'mercenary';
    case TribalWarrior = 'tribal_warrior';
    case SlaveSoldier = 'slave_soldier';
    case FeudalLevy = 'feudal_levy';
    case Volunteer = 'volunteer';
    case Mixed = 'mixed';
    case Unknown = 'unknown';
}
