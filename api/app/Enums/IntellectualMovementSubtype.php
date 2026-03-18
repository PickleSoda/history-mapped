<?php

declare(strict_types=1);

namespace App\Enums;

enum IntellectualMovementSubtype: string
{
    case PhilosophicalSchool = 'philosophical_school';
    case ArtisticStyle = 'artistic_style';
    case LiteraryMovement = 'literary_movement';
    case ScientificParadigm = 'scientific_paradigm';
    case LegalTradition = 'legal_tradition';
    case EducationalTradition = 'educational_tradition';
    case Historiographical = 'historiographical';
    case Other = 'other';
}
