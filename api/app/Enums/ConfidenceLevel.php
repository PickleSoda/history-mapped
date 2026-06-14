<?php

declare(strict_types=1);

namespace App\Enums;

enum ConfidenceLevel: string
{
    case High = 'high';
    case Medium = 'medium';
    case Low = 'low';
    case Unresolved = 'unresolved';

    /**
     * Confidence values at least as confident as $level, least-to-most order.
     *
     * The Postgres enum's storage order does not match confidence magnitude, so
     * a scalar `>=` comparison is wrong — callers should `whereIn(atLeast(...))`.
     *
     * @return list<string>
     */
    public static function atLeast(self $level): array
    {
        $order = [self::Unresolved, self::Low, self::Medium, self::High];
        $index = array_search($level, $order, true);

        return array_map(
            static fn (self $c): string => $c->value,
            array_slice($order, $index === false ? 0 : (int) $index),
        );
    }
}
