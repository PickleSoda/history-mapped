<?php

declare(strict_types=1);

namespace App\Enums;

enum ReliabilityTier: string
{
    case Authoritative = 'authoritative';
    case Scholarly = 'scholarly';
    case Reference = 'reference';
    case UserContributed = 'user_contributed';
}
