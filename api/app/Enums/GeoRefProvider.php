<?php

declare(strict_types=1);

namespace App\Enums;

enum GeoRefProvider: string
{
    case Ohm = 'ohm';
    case Wikidata = 'wikidata';
    case Geonames = 'geonames';
    case Pleiades = 'pleiades';
    case Custom = 'custom';
}
