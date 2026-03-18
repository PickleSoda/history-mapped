<?php

declare(strict_types=1);

namespace App\Enums;

enum SocialClassSubtype: string
{
    case Royalty = 'royalty';
    case Nobility = 'nobility';
    case Clergy = 'clergy';
    case WarriorClass = 'warrior_class';
    case MerchantClass = 'merchant_class';
    case ArtisanClass = 'artisan_class';
    case Peasantry = 'peasantry';
    case Serf = 'serf';
    case Slave = 'slave';
    case Freedman = 'freedman';
    case BureaucratLiterati = 'bureaucrat_literati';
    case NomadPastoral = 'nomad_pastoral';
    case OutcastUntouchable = 'outcast_untouchable';
    case Intelligentsia = 'intelligentsia';
    case Bourgeoisie = 'bourgeoisie';
    case Proletariat = 'proletariat';
    case Other = 'other';
}
