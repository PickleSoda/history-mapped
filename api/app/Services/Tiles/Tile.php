<?php

declare(strict_types=1);

namespace App\Services\Tiles;

/** One rendered tile: the MVT bytes (empty for an empty tile) and the function's cache key (`md5(mvt)`). */
final readonly class Tile
{
    public function __construct(
        public string $mvt,
        public string $key,
    ) {}

    public function isEmpty(): bool
    {
        return $this->mvt === '';
    }
}
