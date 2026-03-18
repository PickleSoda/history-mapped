<?php

declare(strict_types=1);

namespace App\Enums;

enum LanguageStatus: string
{
    case Living = 'living';
    case Extinct = 'extinct';
    case LiturgicalOnly = 'liturgical_only';
    case Reconstructed = 'reconstructed';
    case Endangered = 'endangered';
    case Revived = 'revived';
    case Unknown = 'unknown';
}
