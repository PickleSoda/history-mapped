<?php

declare(strict_types=1);

namespace App\Enums;

enum ResourceStrategicValue: string
{
    case Critical = 'critical';
    case High = 'high';
    case Medium = 'medium';
    case Low = 'low';
    case Negligible = 'negligible';
    case Unknown = 'unknown';
}
