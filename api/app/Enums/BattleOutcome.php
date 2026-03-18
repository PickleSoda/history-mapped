<?php

declare(strict_types=1);

namespace App\Enums;

enum BattleOutcome: string
{
    case DecisiveVictory = 'decisive_victory';
    case TacticalVictory = 'tactical_victory';
    case PyrrhicVictory = 'pyrrhic_victory';
    case Draw = 'draw';
    case TacticalDefeat = 'tactical_defeat';
    case DecisiveDefeat = 'decisive_defeat';
    case Inconclusive = 'inconclusive';
    case Unknown = 'unknown';
}
