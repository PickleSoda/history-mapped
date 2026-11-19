<?php

declare(strict_types=1);

namespace App\Support\Persona;

use App\Enums\EntityType;
use App\Models\Entity;

/**
 * Who can be talked to: a person with a known death year at least
 * `persona.min_years_dead` years ago. Only people today; a city or family
 * speaker would add its own rule here.
 */
final class SpeakerEligibility
{
    public static function minYearsDead(): int
    {
        return max(0, (int) config('persona.min_years_dead', 70));
    }

    /** The latest death year that still qualifies. */
    public static function latestDeathYear(?int $currentYear = null): int
    {
        return ($currentYear ?? (int) now()->year) - self::minYearsDead();
    }

    public static function qualifies(EntityType|string|null $type, ?int $deathYear, ?int $currentYear = null): bool
    {
        $type = $type instanceof EntityType ? $type->value : $type;

        return $type === EntityType::Person->value
            && $deathYear !== null
            && $deathYear <= self::latestDeathYear($currentYear);
    }

    /** The death year the rule reads: the primary range's end year. */
    public static function deathYear(Entity $entity): ?int
    {
        $entity->loadMissing('primaryTemporalRange');

        return $entity->primaryTemporalRange?->end_year;
    }

    public static function isTalkable(Entity $entity): bool
    {
        return self::qualifies($entity->entity_type, self::deathYear($entity));
    }
}
