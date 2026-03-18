<?php

declare(strict_types=1);

namespace App\Enums;

enum EpidemicSubtype: string
{
    case PlagueBacterial = 'plague_bacterial';
    case PlagueViral = 'plague_viral';
    case Smallpox = 'smallpox';
    case Cholera = 'cholera';
    case Malaria = 'malaria';
    case Typhus = 'typhus';
    case Influenza = 'influenza';
    case Tuberculosis = 'tuberculosis';
    case Leprosy = 'leprosy';
    case Dysentery = 'dysentery';
    case Measles = 'measles';
    case UnknownPestilence = 'unknown_pestilence';
    case Other = 'other';
}
