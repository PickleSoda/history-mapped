<?php

declare(strict_types=1);

namespace App\Support\ContentBundle;

/**
 * Export profile. Public drops internal data (`_`-prefixed attributes and geo-ref source_meta).
 */
enum Profile: string
{
    case Full = 'full';
    case Public = 'public';

    /**
     * Apply the profile to a decoded `attributes` value: Public drops `_`-prefixed keys.
     * Works on the stdClass that JsonLine::decodeJsonb() produces.
     */
    public function filterAttributes(mixed $attributes): mixed
    {
        if ($this !== self::Public || ! $attributes instanceof \stdClass) {
            return $attributes;
        }

        return (object) array_filter((array) $attributes, fn ($key) => ! str_starts_with((string) $key, '_'), ARRAY_FILTER_USE_KEY);
    }
}
