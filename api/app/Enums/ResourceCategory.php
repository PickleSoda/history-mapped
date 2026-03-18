<?php

declare(strict_types=1);

namespace App\Enums;

enum ResourceCategory: string
{
    case Grain = 'grain';
    case Livestock = 'livestock';
    case CashCrop = 'cash_crop';
    case Timber = 'timber';
    case MetalPrecious = 'metal_precious';
    case MetalStrategic = 'metal_strategic';
    case MetalBase = 'metal_base';
    case StoneBuilding = 'stone_building';
    case Gemstone = 'gemstone';
    case Salt = 'salt';
    case Spice = 'spice';
    case TextileRaw = 'textile_raw';
    case Dye = 'dye';
    case IncensePerfume = 'incense_perfume';
    case Fuel = 'fuel';
    case Water = 'water';
    case FishSeafood = 'fish_seafood';
    case AnimalStrategic = 'animal_strategic';
    case AnimalLuxury = 'animal_luxury';
    case Medicinal = 'medicinal';
    case Other = 'other';
}
