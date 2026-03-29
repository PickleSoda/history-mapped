<?php

declare(strict_types=1);

namespace App\Enums;

enum GeoRefRetrievalMethod: string
{
    case Overpass = 'overpass';
    case Nominatim = 'nominatim';
    case Rest = 'rest';
    case Manual = 'manual';
}
