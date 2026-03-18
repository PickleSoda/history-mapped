<?php

declare(strict_types=1);

namespace App\Enums;

enum CulturalWorkSubtype: string
{
    case LiteraryText = 'literary_text';
    case PhilosophicalText = 'philosophical_text';
    case HistoricalText = 'historical_text';
    case ReligiousText = 'religious_text';
    case ScientificText = 'scientific_text';
    case LegalText = 'legal_text';
    case BuildingArchitecture = 'building_architecture';
    case Sculpture = 'sculpture';
    case PaintingMural = 'painting_mural';
    case Mosaic = 'mosaic';
    case PotteryCeramics = 'pottery_ceramics';
    case Textile = 'textile';
    case Metalwork = 'metalwork';
    case MusicalComposition = 'musical_composition';
    case Inscription = 'inscription';
    case CoinDesign = 'coin_design';
    case MapCartography = 'map_cartography';
    case Other = 'other';
}
