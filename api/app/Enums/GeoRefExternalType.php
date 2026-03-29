<?php

declare(strict_types=1);

namespace App\Enums;

enum GeoRefExternalType: string
{
    case Node = 'node';
    case Way = 'way';
    case Relation = 'relation';
    case Feature = 'feature';
    case Qid = 'qid';
}
