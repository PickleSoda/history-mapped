<?php

declare(strict_types=1);

namespace App\Enums;

enum TechnologyDomain: string
{
    case Military = 'military';
    case Agricultural = 'agricultural';
    case Industrial = 'industrial';
    case Construction = 'construction';
    case Navigation = 'navigation';
    case Communication = 'communication';
    case Medical = 'medical';
    case Metallurgical = 'metallurgical';
    case Textile = 'textile';
    case WritingPrinting = 'writing_printing';
    case Astronomical = 'astronomical';
    case Hydraulic = 'hydraulic';
    case Transportation = 'transportation';
    case FoodPreservation = 'food_preservation';
    case Other = 'other';
}
