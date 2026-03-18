<?php

declare(strict_types=1);

namespace App\Enums;

enum ReligiousMovementSubtype: string
{
    case Monotheism = 'monotheism';
    case Polytheism = 'polytheism';
    case Animism = 'animism';
    case AncestorWorship = 'ancestor_worship';
    case PhilosophicalReligion = 'philosophical_religion';
    case MysteryCult = 'mystery_cult';
    case Syncretic = 'syncretic';
    case SectDenomination = 'sect_denomination';
    case HereticalMovement = 'heretical_movement';
    case ReformMovement = 'reform_movement';
    case MissionaryMovement = 'missionary_movement';
    case MonasticOrder = 'monastic_order';
    case Other = 'other';
}
