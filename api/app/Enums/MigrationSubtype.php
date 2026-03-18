<?php

declare(strict_types=1);

namespace App\Enums;

enum MigrationSubtype: string
{
    case Invasion = 'invasion';
    case Colonization = 'colonization';
    case ForcedDeportation = 'forced_deportation';
    case RefugeeFlight = 'refugee_flight';
    case EconomicMigration = 'economic_migration';
    case NomadicMovement = 'nomadic_movement';
    case PilgrimageSettlement = 'pilgrimage_settlement';
    case SlaveTrade = 'slave_trade';
    case Diaspora = 'diaspora';
    case Other = 'other';
}
