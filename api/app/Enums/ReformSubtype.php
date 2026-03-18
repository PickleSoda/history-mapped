<?php

declare(strict_types=1);

namespace App\Enums;

enum ReformSubtype: string
{
    case LegalCode = 'legal_code';
    case ConstitutionalChange = 'constitutional_change';
    case AdministrativeReorganization = 'administrative_reorganization';
    case LandReform = 'land_reform';
    case TaxationReform = 'taxation_reform';
    case MilitaryReform = 'military_reform';
    case ReligiousReform = 'religious_reform';
    case EducationalReform = 'educational_reform';
    case EconomicReform = 'economic_reform';
    case Abolition = 'abolition';
    case Enfranchisement = 'enfranchisement';
    case Other = 'other';
}
