<?php

declare(strict_types=1);

namespace App\Enums;

enum ChronicleEntryRole: string
{
    case Participant = 'participant';
    case Mentioned = 'mentioned';
    case Location = 'location';
    case Outcome = 'outcome';
}
