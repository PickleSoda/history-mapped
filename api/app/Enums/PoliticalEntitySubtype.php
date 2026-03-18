<?php

declare(strict_types=1);

namespace App\Enums;

enum PoliticalEntitySubtype: string
{
    case Empire = 'empire';
    case Kingdom = 'kingdom';
    case Republic = 'republic';
    case CityState = 'city_state';
    case TribalConfederation = 'tribal_confederation';
    case Theocracy = 'theocracy';
    case Principality = 'principality';
    case Duchy = 'duchy';
    case Khanate = 'khanate';
    case Sultanate = 'sultanate';
    case Caliphate = 'caliphate';
    case Shogunate = 'shogunate';
    case Confederation = 'confederation';
    case League = 'league';
    case ColonialTerritory = 'colonial_territory';
    case Protectorate = 'protectorate';
    case VassalState = 'vassal_state';
    case FreeCity = 'free_city';
    case NomadicPolity = 'nomadic_polity';
    case Other = 'other';
}
