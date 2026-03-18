<?php

declare(strict_types=1);

namespace App\Enums;

enum DurationType: string
{
    case Point = 'point';
    case Period = 'period';
    case Ongoing = 'ongoing';
    case Uncertain = 'uncertain';
}
