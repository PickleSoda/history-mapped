<?php

declare(strict_types=1);

namespace App\Enums;

enum TreatySubtype: string
{
    case PeaceTreaty = 'peace_treaty';
    case AllianceTreaty = 'alliance_treaty';
    case TradeAgreement = 'trade_agreement';
    case MarriageAlliance = 'marriage_alliance';
    case TributeAgreement = 'tribute_agreement';
    case BorderDemarcation = 'border_demarcation';
    case NonAggressionPact = 'non_aggression_pact';
    case Surrender = 'surrender';
    case Ceasefire = 'ceasefire';
    case MutualDefense = 'mutual_defense';
    case VassalageAgreement = 'vassalage_agreement';
    case Other = 'other';
}
