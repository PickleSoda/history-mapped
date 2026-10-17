<?php

declare(strict_types=1);

namespace App\Enums;

/**
 * The dimension a tag describes. Every facet but Topic is a controlled
 * vocabulary (database/data/tags/vocabulary.json); Topic tags are free-form
 * and created on demand when an admin or the pipeline supplies an unknown tag.
 */
enum TagFacet: string
{
    case Era = 'era';
    case Region = 'region';
    case Theme = 'theme';
    case Type = 'type';
    case Topic = 'topic';

    public function label(): string
    {
        return match ($this) {
            self::Era => 'Era',
            self::Region => 'Region',
            self::Theme => 'Theme',
            self::Type => 'Type',
            self::Topic => 'Topic',
        };
    }
}
