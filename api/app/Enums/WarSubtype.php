<?php

declare(strict_types=1);

namespace App\Enums;

enum WarSubtype: string
{
    case InterstateWar = 'interstate_war';
    case CivilWar = 'civil_war';
    case ColonialWar = 'colonial_war';
    case ReligiousWar = 'religious_war';
    case SuccessionWar = 'succession_war';
    case TradeWar = 'trade_war';
    case BorderConflict = 'border_conflict';
    case RaidSeries = 'raid_series';
    case Invasion = 'invasion';
    case SiegeCampaign = 'siege_campaign';
    case NavalWar = 'naval_war';
    case TribalWar = 'tribal_war';
    case Other = 'other';
}
