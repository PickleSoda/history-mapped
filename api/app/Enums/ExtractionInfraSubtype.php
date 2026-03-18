<?php

declare(strict_types=1);

namespace App\Enums;

enum ExtractionInfraSubtype: string
{
    case Mine = 'mine';
    case Quarry = 'quarry';
    case Farm = 'farm';
    case Plantation = 'plantation';
    case Ranch = 'ranch';
    case Fishery = 'fishery';
    case ForestLogging = 'forest_logging';
    case HuntingGround = 'hunting_ground';
    case WellSpring = 'well_spring';
    case SaltWorks = 'salt_works';
    case Workshop = 'workshop';
    case Shipyard = 'shipyard';
    case SmithyFoundry = 'smithy_foundry';
    case IrrigationSystem = 'irrigation_system';
    case Mill = 'mill';
    case Vineyard = 'vineyard';
    case Kiln = 'kiln';
    case Other = 'other';
}
