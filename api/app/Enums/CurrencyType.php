<?php

declare(strict_types=1);

namespace App\Enums;

enum CurrencyType: string
{
    case CoinMetal = 'coin_metal';
    case Paper = 'paper';
    case CommodityMoney = 'commodity_money';
    case ShellBead = 'shell_bead';
    case BarterSystem = 'barter_system';
    case CreditSystem = 'credit_system';
    case Other = 'other';
}
