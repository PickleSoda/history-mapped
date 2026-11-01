<?php

declare(strict_types=1);

namespace App\Services\Tiles;

use InvalidArgumentException;

final class UnknownTileSource extends InvalidArgumentException
{
    public static function named(string $source): self
    {
        return new self("Unknown tile source '{$source}'.");
    }
}
