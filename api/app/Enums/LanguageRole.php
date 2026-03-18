<?php

declare(strict_types=1);

namespace App\Enums;

enum LanguageRole: string
{
    case Vernacular = 'vernacular';
    case LinguaFranca = 'lingua_franca';
    case Administrative = 'administrative';
    case Liturgical = 'liturgical';
    case Literary = 'literary';
    case TradeLanguage = 'trade_language';
    case CourtLanguage = 'court_language';
    case Scholarly = 'scholarly';
    case Other = 'other';
}
