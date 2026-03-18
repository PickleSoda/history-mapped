<?php

declare(strict_types=1);

namespace App\Enums;

enum SuccessionType: string
{
    case Primogeniture = 'primogeniture';
    case Ultimogeniture = 'ultimogeniture';
    case Elective = 'elective';
    case Tanistry = 'tanistry';
    case Agnatic = 'agnatic';
    case Cognatic = 'cognatic';
    case Appointed = 'appointed';
    case Meritocratic = 'meritocratic';
    case MilitaryAcclamation = 'military_acclamation';
    case DivineSelection = 'divine_selection';
    case Rotation = 'rotation';
    case Other = 'other';
    case Unknown = 'unknown';
}
