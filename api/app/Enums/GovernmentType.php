<?php

declare(strict_types=1);

namespace App\Enums;

enum GovernmentType: string
{
    case AbsoluteMonarchy = 'absolute_monarchy';
    case ConstitutionalMonarchy = 'constitutional_monarchy';
    case ElectiveMonarchy = 'elective_monarchy';
    case Oligarchy = 'oligarchy';
    case AristocraticRepublic = 'aristocratic_republic';
    case DemocraticRepublic = 'democratic_republic';
    case Theocracy = 'theocracy';
    case MilitaryDictatorship = 'military_dictatorship';
    case TribalChieftainship = 'tribal_chieftainship';
    case Feudal = 'feudal';
    case BureaucraticCentralized = 'bureaucratic_centralized';
    case ColonialAdministration = 'colonial_administration';
    case CommunistState = 'communist_state';
    case FascistState = 'fascist_state';
    case Anarchy = 'anarchy';
    case Diarchy = 'diarchy';
    case Federal = 'federal';
    case Confederal = 'confederal';
    case Other = 'other';
}
