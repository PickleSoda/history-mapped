<?php

declare(strict_types=1);

namespace App\Enums;

enum DisasterSubtype: string
{
    case Earthquake = 'earthquake';
    case VolcanicEruption = 'volcanic_eruption';
    case Flood = 'flood';
    case Tsunami = 'tsunami';
    case Drought = 'drought';
    case Famine = 'famine';
    case Wildfire = 'wildfire';
    case HurricaneTyphoon = 'hurricane_typhoon';
    case Landslide = 'landslide';
    case ClimateShift = 'climate_shift';
    case Other = 'other';
}
