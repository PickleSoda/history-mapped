<?php

declare(strict_types=1);

namespace App\Enums;

enum MonumentSubtype: string
{
    case Palace = 'palace';
    case Forum = 'forum';
    case Amphitheater = 'amphitheater';
    case Theater = 'theater';
    case BathComplex = 'bath_complex';
    case Library = 'library';
    case MarketAgora = 'market_agora';
    case GovernmentBuilding = 'government_building';
    case Temple = 'temple';
    case Cathedral = 'cathedral';
    case Mosque = 'mosque';
    case Monastery = 'monastery';
    case Shrine = 'shrine';
    case Pyramid = 'pyramid';
    case MegalithicStructure = 'megalithic_structure';
    case SacredGrove = 'sacred_grove';
    case Fortification = 'fortification';
    case Wall = 'wall';
    case Castle = 'castle';
    case Citadel = 'citadel';
    case Watchtower = 'watchtower';
    case Aqueduct = 'aqueduct';
    case Canal = 'canal';
    case Bridge = 'bridge';
    case RoadSection = 'road_section';
    case Harbor = 'harbor';
    case Lighthouse = 'lighthouse';
    case Dam = 'dam';
    case Granary = 'granary';
    case SewerSystem = 'sewer_system';
    case TriumphalArch = 'triumphal_arch';
    case Obelisk = 'obelisk';
    case Mausoleum = 'mausoleum';
    case Tomb = 'tomb';
    case Statue = 'statue';
    case Memorial = 'memorial';
    case Stele = 'stele';
    case Other = 'other';
}
