<?php

declare(strict_types=1);

namespace App\Enums;

enum GeometryType: string
{
    case Point = 'point';
    case Polygon = 'polygon';
    case Linestring = 'linestring';
    case Multipoint = 'multipoint';
    case Multipolygon = 'multipolygon';
}
