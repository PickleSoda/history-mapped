<?php

declare(strict_types=1);

namespace App\Enums;

enum GeoRefMatchRole: string
{
    case Primary = 'primary';
    case Candidate = 'candidate';
    case Fallback = 'fallback';
    case Rejected = 'rejected';
}
