<?php

declare(strict_types=1);

namespace App\Enums;

enum BattleSubtype: string
{
    case PitchedBattle = 'pitched_battle';
    case Siege = 'siege';
    case NavalBattle = 'naval_battle';
    case Ambush = 'ambush';
    case Skirmish = 'skirmish';
    case Raid = 'raid';
    case LastStand = 'last_stand';
    case Other = 'other';
}
