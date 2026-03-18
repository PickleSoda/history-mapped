<?php

declare(strict_types=1);

namespace App\Enums;

enum PersonRole: string
{
    case Ruler = 'ruler';
    case Regent = 'regent';
    case Heir = 'heir';
    case Consort = 'consort';
    case General = 'general';
    case Admiral = 'admiral';
    case Diplomat = 'diplomat';
    case Governor = 'governor';
    case ReligiousLeader = 'religious_leader';
    case Prophet = 'prophet';
    case Philosopher = 'philosopher';
    case Scientist = 'scientist';
    case Artist = 'artist';
    case Architect = 'architect';
    case Poet = 'poet';
    case Historian = 'historian';
    case Lawgiver = 'lawgiver';
    case RebelLeader = 'rebel_leader';
    case Merchant = 'merchant';
    case Explorer = 'explorer';
    case Spy = 'spy';
    case Slave = 'slave';
    case Other = 'other';
}
