<?php

declare(strict_types=1);

namespace App\Enums;

enum SettlementSubtype: string
{
    case CapitalCity = 'capital_city';
    case MajorCity = 'major_city';
    case MinorCity = 'minor_city';
    case Town = 'town';
    case Village = 'village';
    case Fortress = 'fortress';
    case Port = 'port';
    case ReligiousCenter = 'religious_center';
    case TradeHub = 'trade_hub';
    case AdministrativeCenter = 'administrative_center';
    case MiningTown = 'mining_town';
    case Oasis = 'oasis';
    case Colony = 'colony';
    case GarrisonTown = 'garrison_town';
    case Abandoned = 'abandoned';
    case Other = 'other';
}
