<?php

declare(strict_types=1);

namespace App\Enums;

enum EpidemicSeverity: string
{
    case Local = 'local';
    case Regional = 'regional';
    case Pandemic = 'pandemic';
    case Unknown = 'unknown';
}
