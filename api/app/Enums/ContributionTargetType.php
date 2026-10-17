<?php

declare(strict_types=1);

namespace App\Enums;

use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use App\Models\EntityRelationship;
use App\Support\ContributionFields;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Support\Str;

/**
 * Records a contributor may correct, and the prose fields open to correction
 * on each. Anything not listed here is editorial-only (admin panel).
 */
enum ContributionTargetType: string
{
    case Entity = 'entity';
    case Relationship = 'relationship';
    case Chronicle = 'chronicle';
    case ChronicleEntry = 'chronicle_entry';

    /** Longest proposed text accepted for a prose field. */
    public const MAX_TEXT_LENGTH = 10000;

    /** Longest proposed text accepted for a one-line field (name / title). */
    public const MAX_LINE_LENGTH = 255;

    /** @return class-string<Model> */
    public function modelClass(): string
    {
        return match ($this) {
            self::Entity => Entity::class,
            self::Relationship => EntityRelationship::class,
            self::Chronicle => Chronicle::class,
            self::ChronicleEntry => ChronicleEntry::class,
        };
    }

    /** @return list<string> */
    public function editableFields(): array
    {
        return match ($this) {
            self::Entity => ['name', 'summary', 'significance', 'aliases'],
            self::Relationship => ['description'],
            self::Chronicle => ['title'],
            self::ChronicleEntry => ['narrative_text'],
        };
    }

    /** One-line fields must stay non-empty and short. */
    public function isLineField(string $field): bool
    {
        return ContributionFields::isLine($field);
    }

    public function maxLength(string $field): int
    {
        return $this->isLineField($field) ? self::MAX_LINE_LENGTH : self::MAX_TEXT_LENGTH;
    }

    /** Primary keys are Postgres `uuid`s; anything else cannot match. */
    public function find(string $id): ?Model
    {
        $class = $this->modelClass();

        return Str::isUuid($id) ? $class::query()->find($id) : null;
    }
}
