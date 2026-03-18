<?php

declare(strict_types=1);

namespace App\Enums;

enum DiplomaticStatus: string
{
    case Alliance = 'alliance';
    case DefensivePact = 'defensive_pact';
    case TradeAgreement = 'trade_agreement';
    case Vassalage = 'vassalage';
    case Tributary = 'tributary';
    case Protectorate = 'protectorate';
    case PersonalUnion = 'personal_union';
    case FederationMember = 'federation_member';
    case NonAggression = 'non_aggression';
    case Neutrality = 'neutrality';
    case War = 'war';
    case ColdWar = 'cold_war';
    case Embargo = 'embargo';
    case Occupation = 'occupation';
    case Other = 'other';
}
