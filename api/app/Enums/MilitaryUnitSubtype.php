<?php

declare(strict_types=1);

namespace App\Enums;

enum MilitaryUnitSubtype: string
{
    case Infantry = 'infantry';
    case Cavalry = 'cavalry';
    case Navy = 'navy';
    case ArcherRanged = 'archer_ranged';
    case Siege = 'siege';
    case Chariot = 'chariot';
    case ElephantCorps = 'elephant_corps';
    case Garrison = 'garrison';
    case MercenaryCompany = 'mercenary_company';
    case Legion = 'legion';
    case Phalanx = 'phalanx';
    case Warband = 'warband';
    case Fleet = 'fleet';
    case AirForce = 'air_force';
    case SpecialForces = 'special_forces';
    case Militia = 'militia';
    case Guard = 'guard';
    case Other = 'other';
}
